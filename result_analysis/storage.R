library(here)
library(lubridate)

options(googleAuthR.scopes.selected = "https://www.googleapis.com/auth/cloud-platform")
library(googleCloudStorageR)


.result_analysis_dir = paste0(here(), "/result_analysis")

.graph_file_manifest = NULL

STORAGE_BUCKET = NULL

# See "predefinedAcl" under https://code.markedmondson.me/googleCloudStorageR/reference/gcs_upload.html
STORAGE_PREDEFINED_ACL = "bucketLevel" # "private"

# The subdirectory to upload this analysis under in cloud storage.  This should
# not start with a "/" character.
STORAGE_BASE_DIR = "equitable-polling-locations-analyses"

# The name of this analysis in cloud storage
CLOUD_STORAGE_ANALYSIS_NAME = NULL

create_graph_file_manifest <- function() {
	list(
		model_run_ids = c(),
		graph_files = c(),
        created_at = now(tzone = "UTC")
	)
}

get_graph_file_manifest <- function() {
	if (is.null(.graph_file_manifest)) {
		.graph_file_manifest <<- create_graph_file_manifest()
	}

	.graph_file_manifest
}

clear_graph_file_manifest <- function() {
	.graph_file_manifest = NULL
}

add_model_run_id_to_graph_file_manifest <- function(model_run_id) {
    if (is.null(model_run_id) || nchar(model_run_id) == 0) {
		# Handle null or empty string cases
		stop(paste0("add_model_run_id_to_graph_file_manifest got an invalid model_run_id "), model_run_id)
	}

    # Init .graph_file_manifest if it doesn't already exist
	get_graph_file_manifest()

	.graph_file_manifest$model_run_ids <<- unique(c(.graph_file_manifest$model_run_ids, model_run_id))

    model_run_id
}

add_graph_to_graph_file_manifest <- function(graph_file) {
    if (startsWith(graph_file, "/")) {
        graph_file_path = graph_file
    } else {
        graph_file_path <- file.path(getwd(), graph_file)
    }

    if (startsWith(graph_file_path, .result_analysis_dir)) {
        # Strip off ../result_analysis graph_file_path
        # but keep any subsequent sub-directories after it.
        graph_file_path <- substring(graph_file_path, nchar(.result_analysis_dir) + 2)
    }

    if (is.null(graph_file_path) || nchar(graph_file_path) == 0) {
		# Handle null or empty string cases
		stop(paste0("add_graph_file_to_graph_file_manifest got an invalid graph_file_path "), graph_file_path)
	}

    # Init .graph_file_manifest if it doesn't already exist
	get_graph_file_manifest()

	.graph_file_manifest$graph_files <<- unique(c(.graph_file_manifest$graph_files, graph_file_path))

    graph_file_path
}

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

    date_stamp = format(manifest$created_at, "%Y%m%d-%H%M%S")
    cloud_storage_base_path <- paste(STORAGE_BASE_DIR, CLOUD_STORAGE_ANALYSIS_NAME, date_stamp, sep="/")

    for (graph_file in manifest$graph_files) {
        local_file_path <- paste(.result_analysis_dir, graph_file, sep="/")
        cloud_storage_file_name <- paste(cloud_storage_base_path, graph_file, sep="/")

        if (file.exists(local_file_path)) {
            print(paste0("Uploading file ", local_file_path, " -> ", STORAGE_BUCKET, ":", cloud_storage_file_name))
            gcs_upload(file=local_file_path, bucket=STORAGE_BUCKET, name=cloud_storage_file_name, predefinedAcl=STORAGE_PREDEFINED_ACL)
        } else {
            print(paste0("Cannot find file ", local_file_path))
        }
    }
}