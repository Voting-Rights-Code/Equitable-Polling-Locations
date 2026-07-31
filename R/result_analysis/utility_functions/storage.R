library(here)
library(lubridate)
library(yaml)

options(googleAuthR.scopes.selected = "https://www.googleapis.com/auth/cloud-platform")
library(googleCloudStorageR)


.result_analysis_dir = paste0(here(), "/result_analysis_outputs")
.precinct_analysis_dir = paste0(here(), "/precinct_analysis_outputs")

valid_directories <- c(.result_analysis_dir, .precinct_analysis_dir)
.graph_file_manifest = NULL

STORAGE_BUCKET = NULL

# See "predefinedAcl" under https://code.markedmondson.me/googleCloudStorageR/reference/gcs_upload.html
STORAGE_PREDEFINED_ACL = "bucketLevel" # "private"

# The subdirectory to upload this analysis under in cloud storage.  This should
# not start with a "/" character.
STORAGE_BASE_DIR = "equitable-polling-locations-analyses"

# The name of this analysis in cloud storage
CLOUD_STORAGE_ANALYSIS_NAME = NULL

# The name to use for manifest files
ANALYSIS_MANIFEST = "analysis_manifest.yaml"


# Create a manifest on sources for data as well as outputed graphs
# for an analysis.
create_graph_file_manifest <- function() {
	list(
        # The name of this analysis, will default to CLOUD_STORAGE_ANALYSIS_NAME
        analysis_name = NULL,
        # The list of information on all configs used, each element containing config id ($id),
        # config set ($config_set), and config name ($config_name)
        configs = list(),
        # The list of all unique model_run_ids used in this analsysis
		model_run_ids = c(),
        # The graphs files generated
		graph_files = c(),
        # The date and time this analsis was run
        created_at = now(tzone = "UTC")
	)
}

# Return the global singelton instance of the graph_file_manifest.
# A new instance will be created if one does not already exist.
get_graph_file_manifest <- function() {
	if (is.null(.graph_file_manifest)) {
		.graph_file_manifest <<- create_graph_file_manifest()
	}

	.graph_file_manifest
}

# Clear the graph_file_manifest. Calling get_graph_file_manifest
# after this function will start with a clear one.
clear_graph_file_manifest <- function() {
	.graph_file_manifest = NULL
}

# Uniquely add a model_run_id to the graph_file_manifest.
#
# model_run_id: string of the model_run_id
add_model_run_id_to_graph_file_manifest <- function(model_run_id) {
    if (nchar(model_run_id) == 0) {
		# Handle null or empty string cases
		stop(paste0("add_model_run_id_to_graph_file_manifest got an invalid model_run_id ", model_run_id))
	}

    # Init .graph_file_manifest if it doesn't already exist
	get_graph_file_manifest()

	.graph_file_manifest$model_run_ids <<- unique(c(.graph_file_manifest$model_run_ids, model_run_id))

    model_run_id
}

# Add config info to the graph_file_manifest.
#
# config_id: string id of the config
# config_set: string of the config set
# config_name: string of the config name
add_config_info_to_graph_file_manifest <- function(config_id, config_set, config_name) {
    if (nchar(config_id) == 0) {
		# Handle null or empty string cases
		stop(paste0("add_config_info_to_graph_file_manifest got an invalid config_id ", config_id))
	}

    if (nchar(config_set) == 0) {
		# Handle null or empty string cases
		stop(paste0("add_config_info_to_graph_file_manifest got an invalid config_set ", config_set))
	}

    if (nchar(config_name) == 0) {
		# Handle null or empty string cases
		stop(paste0("add_config_info_to_graph_file_manifest got an invalid config_name ", config_name))
	}

    # Init .graph_file_manifest if it doesn't already exist
	get_graph_file_manifest()

    config_info = list(
        id = config_id,
        config_set = config_set,
        config_name = config_name
    )

    num_configs = length(.graph_file_manifest$configs)
	.graph_file_manifest$configs[[num_configs + 1]] <<- config_info

    config_info
}

# Uniquely add a graph file path to the graph_file_manifest.
#
# graph_file: string of the path to the graph file, relative paths will be
#    automatically resolved.
add_graph_to_graph_file_manifest <- function(graph_file) {
    if (nchar(graph_file) <=1) {
		# Handle null or empty string cases
		stop(paste0("add_graph_to_graph_file_manifest got an invalid graph_file_path ", graph_file))
	}
    graph_file_path <- file.path(getwd(), graph_file)

    parent_dir <- valid_directories[startsWith(graph_file_path, valid_directories)]
    if (length(parent_dir) == 0) {
        stop('trying to upload a file in an unsupported directory')
    }

    # Strip off the root directory from graph_file_path
    # but keep any subsequent sub-directories after it.
    root_dir <- here()
    graph_file_path <- substring(graph_file_path, nchar(root_dir) + 2)

    # Init .graph_file_manifest if it doesn't already exist
	get_graph_file_manifest()

	.graph_file_manifest$graph_files <<- unique(c(.graph_file_manifest$graph_files, graph_file_path))

    graph_file_path
}

# Uploads all files in the manifest to Google Cloud Storage.
upload_graph_files_to_cloud_storage <- function() {
    manifest = get_graph_file_manifest()
    if (length(manifest$graph_files) < 1) {
        stop("No files to upload to cloud storage")
    }

    if (is.null(STORAGE_BASE_DIR) || nchar(STORAGE_BASE_DIR) == 0) {
        stop("Invalid STORAGE_BASE_DIR")
    }

    if (is.null(STORAGE_BUCKET) || nchar(STORAGE_BUCKET) == 0) {
        stop("Invalid STORAGE_BUCKET")
    }

    if (is.null(CLOUD_STORAGE_ANALYSIS_NAME) || nchar(CLOUD_STORAGE_ANALYSIS_NAME) == 0) {
        stop("Invalid CLOUD_STORAGE_ANALYSIS_NAME")
    }

    manifest$analysis_name <- CLOUD_STORAGE_ANALYSIS_NAME

    date_stamp = format(manifest$created_at, "%Y%m%d-%H%M%S")
    cloud_storage_base_path <- paste(STORAGE_BASE_DIR, CLOUD_STORAGE_ANALYSIS_NAME, date_stamp, sep="/")

    # Upload each graph file found in the manifest
    for (graph_file in manifest$graph_files) { 
        
        # define further file name strings for uploads and checks
        local_file_path <- paste(here(), graph_file, sep="/")

        #check that the parent directory is in the group of valid directories
        parent_dir <- valid_directories[startsWith(local_file_path, valid_directories)]

        file_name <- substring(local_file_path, nchar(parent_dir) + 2)
        cloud_storage_file_name <- paste(cloud_storage_base_path, file_name, sep="/")

        #Check that the path still exists and upload
        if (file.exists(local_file_path)) {
            print(paste0("Uploading file ", local_file_path, " -> ", STORAGE_BUCKET, ":", cloud_storage_file_name))
            gcs_upload(file=local_file_path, bucket=STORAGE_BUCKET, name=cloud_storage_file_name, predefinedAcl=STORAGE_PREDEFINED_ACL)
        } else {
            stop(paste0("upload_graph_files_to_cloud_storage cannot find file ", local_file_path))
        }
    
    }

    # Upload the manifest of this analysis to cloud storage
    manifest_copy <- manifest
    manifest_copy$created_at <- format(manifest_copy$created_at, "%Y-%m-%d %H:%M:%S UTC")
    manifest_yaml <- as.yaml(manifest_copy)
    temp_file <- tempfile()
    writeLines(manifest_yaml, temp_file)
    cloud_storage_manifest_file_name = paste(cloud_storage_base_path, ANALYSIS_MANIFEST, sep="/")
    gcs_upload(file=temp_file, bucket=STORAGE_BUCKET, name=cloud_storage_manifest_file_name, predefinedAcl=STORAGE_PREDEFINED_ACL)

    # Return the manifest instance
    manifest
}