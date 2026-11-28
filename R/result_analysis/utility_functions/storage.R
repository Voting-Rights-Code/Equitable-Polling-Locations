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

# The folder inside STORAGE_BUCKET that this analysis uploads under. It is not a
# local path and must not start with a "/". Each analysis script sets its own
# folder before it loads its config. The folder varies by script, not by config.
STORAGE_BASE_DIR = NULL

# The name of this analysis in cloud storage
CLOUD_STORAGE_ANALYSIS_NAME = NULL

# The folder between the analysis name and the datestamp that names the thing
# delivered, not the script that made it (e.g. "distance_analysis"). Each
# analysis script sets its own value with set_cloud_storage_deliverable(), not
# the config, because it varies by script; every script that uploads under
# precinct-distance-analyses/ sets it. NULL or an empty string means unset.
# Unlike STORAGE_BASE_DIR, unset does not stop the run: the upload path then has
# three parts, without this folder.
CLOUD_STORAGE_DELIVERABLE <- NULL

# Every deliverable that exists. A new deliverable adds its name here, so that a
# misspelled name stops the run instead of making a second folder in the bucket.
KNOWN_DELIVERABLES <- c("distance_analysis", "flagged_precincts", "precinct_2_a_b_split")

# An input in git with an uncommitted change stops the run: the manifest says
# "this input at this commit", and the copy on disk is not that copy. A developer
# can set this to TRUE before the first registration to continue; the input is
# then recorded with `uncommitted: true` and is not uploaded. For development
# runs only: do not commit a script or a config that sets it.
ALLOW_UNCOMMITTED_SOURCES <- FALSE

# The name to use for manifest files
ANALYSIS_MANIFEST = "analysis_manifest.yaml"


# Create a manifest on sources for data as well as outputed graphs
# for an analysis.
create_graph_file_manifest <- function() {
	list(
        # The name of this analysis, will default to CLOUD_STORAGE_ANALYSIS_NAME
        analysis_name = NULL,
        # The deliverable folder, set from CLOUD_STORAGE_DELIVERABLE at upload.
        # Left out of the written manifest when that is unset.
        deliverable = NULL,
        # The commit of the checkout, recorded by the first input in git. Left
        # out of the written manifest when no input is in git.
        commit = NULL,
        # The list of information on all configs used, each element containing config id ($id),
        # config set ($config_set), and config name ($config_name)
        configs = list(),
        # The list of all unique model_run_ids used in this analsysis
		model_run_ids = c(),
        # The graphs files generated
		graph_files = c(),
        # Name of the local output folder (e.g. "result_analysis_outputs") that every
        # graph_files entry is relative to. Initialized as NULL and set by the first file added.
        output_tree = NULL,
        # Inputs the analysis consumed, files or folders. Each entry records a
        # role, the repo-relative path it came from (origin) and a kind:
        #   git     tracked and unchanged: found at `commit`, not uploaded
        #   upload  not tracked: uploaded under object_name
        #   census  census data, named by location and census_year, not uploaded
        sources = list(),
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
	.graph_file_manifest <<- NULL
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
    # config_id may be empty: it is a database concept, and configs recovered
    # from a results CSV filename carry only config_set and config_name.

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

    # The trailing "/" anchors the match, so a sibling directory that only
    # shares a prefix (e.g. a result_analysis_outputs_extra) is rejected.
    parent_dir <- valid_directories[startsWith(graph_file_path, paste0(valid_directories, "/"))]
    if (length(parent_dir) == 0) {
        stop(paste0("cannot record graph file ", graph_file_path,
                    " -- not under a supported output directory (",
                    paste(valid_directories, collapse = ", "), ")"))
    }

    # Init .graph_file_manifest if it doesn't already exist
	get_graph_file_manifest()

    # A manifest holds files from one output folder only: the first file
    # added sets it, and a file from the other folder stops the script.
    parent_dir_name <- basename(parent_dir)
    if (is.null(.graph_file_manifest$output_tree)) {
        .graph_file_manifest$output_tree <<- parent_dir_name
    } else if (.graph_file_manifest$output_tree != parent_dir_name) {
        stop(paste0("cannot record graph file ", graph_file_path,
                    " -- this manifest already holds files from ",
                    .graph_file_manifest$output_tree,
                    "; call clear_graph_file_manifest() to start a new analysis"))
    }

    # Strip the output folder off graph_file_path, keeping any subfolders,
    # so each entry is also its cloud object name.
    graph_file_path <- substring(graph_file_path, nchar(parent_dir) + 2)

	.graph_file_manifest$graph_files <<- unique(c(.graph_file_manifest$graph_files, graph_file_path))

    graph_file_path
}

# Runs git in root. Any exit status that is not expected stops with git's own
# message, so that a git failure is never read as an answer. stderr is kept
# apart from the output, so that a git warning is never read as a status line.
run_git <- function(root, git_args, expected_status = 0) {
    if (!nzchar(Sys.which("git"))) {
        stop("git cannot answer: git is not installed")
    }
    stderr_file <- tempfile()
    on.exit(unlink(stderr_file))
    # A non-zero exit also warns; the status is checked below instead
    output <- suppressWarnings(
        system2("git", shQuote(c("-C", root, git_args)), stdout = TRUE, stderr = stderr_file)
    )
    status <- attr(output, "status")
    if (is.null(status)) {
        status <- 0
    }
    if (!(status %in% expected_status)) {
        stop(paste0("git cannot answer in ", root, ": `git ", paste(git_args, collapse = " "),
                    "` exited with status ", status, ". ",
                    paste(readLines(stderr_file, warn = FALSE), collapse = " ")))
    }
    list(output = as.vector(output), status = status)
}

# The commit of the checkout. This and get_git_source_status() hold all git
# access, so that the harness can replace them with stubs.
get_git_head_commit <- function(root = here()) {
    run_git(root, c("rev-parse", "HEAD"))$output
}

# "clean", "modified" or "untracked" for one repo-relative file or folder. It
# asks first whether git tracks the path, because `git status` alone prints
# nothing for an ignored file that is not tracked (.gitignore ignores *.csv).
get_git_source_status <- function(origin, root = here()) {
    if (!nzchar(Sys.which("git-lfs"))) {
        stop("git cannot answer: git-lfs is not installed")
    }
    # Exit status 1 means no tracked file matches the path
    tracked <- run_git(root, c("ls-files", "--error-unmatch", "--", origin),
                       expected_status = c(0, 1))
    if (tracked$status == 1) {
        return("untracked")
    }
    changes <- run_git(root, c("--no-optional-locks", "status", "--porcelain", "--", origin))$output
    if (length(changes) == 0) "clean" else "modified"
}

# The checks every registration makes: a role, and a path that exists below the
# repo root. Returns the repo-relative path.
get_source_origin <- function(role, source_file) {
    if (nchar(role) == 0 || nchar(source_file) <= 1) {
        stop(paste0("cannot record a source: invalid role or path: '",
                    role, "' '", source_file, "'"))
    }
    source_path <- file.path(getwd(), source_file)
    root_prefix <- paste0(here(), "/")
    if (!startsWith(source_path, root_prefix)) {
        stop(paste0("cannot record source file ", source_path,
                    " -- not under the repo root ", here()))
    }
    if (!file.exists(source_path)) {
        stop(paste0("cannot record source file ", source_path,
                    " -- file does not exist"))
    }

    substring(source_path, nchar(root_prefix) + 1)
}

# TRUE when the manifest already records this origin
is_source_recorded <- function(origin) {
    any(vapply(get_graph_file_manifest()$sources,
               function(existing) existing$origin == origin, logical(1)))
}

# Adds one entry to the manifest's sources, once per origin
record_source <- function(source_entry) {
    if (!is_source_recorded(source_entry$origin)) {
        num_sources <- length(.graph_file_manifest$sources)
        .graph_file_manifest$sources[[num_sources + 1]] <<- source_entry
    }

    source_entry
}

# Register an input the analysis consumed, a file or a folder. Unlike graph
# files, sources may live anywhere under the repo root (e.g. datasets/driving/).
# An input in git is not uploaded: its path and the commit already name it. An
# input that git does not track uploads under sources/<basename> beside the
# graphs. Register an input before reading it, so that a problem stops the run
# before any output is built.
#
# role: short label for what the input is (e.g. "driving_distances")
# source_file: path to the file or folder, relative paths resolved against getwd()
add_source_to_graph_file_manifest <- function(role, source_file) {
    origin <- get_source_origin(role, source_file)
    source_status <- get_git_source_status(origin)
    source_entry <- list(role = role, origin = origin)

    if (source_status == "untracked") {
        if (dir.exists(file.path(here(), origin))) {
            stop(paste0("cannot record source folder ", origin, " -- git does not track it, ",
                        "and storage.R cannot upload a folder"))
        }
        source_entry$kind <- "upload"
        source_entry$object_name <- paste0("sources/", basename(origin))
        return(record_source(source_entry))
    }

    if (source_status == "modified" && !isTRUE(ALLOW_UNCOMMITTED_SOURCES)) {
        stop(paste0("cannot record source ", origin, " -- it has an uncommitted change. ",
                    "Commit it, or for a development run set ALLOW_UNCOMMITTED_SOURCES <- TRUE"))
    }
    source_entry$kind <- "git"
    if (source_status == "modified") {
        source_entry$uncommitted <- TRUE
    }

    # One commit per run: the first git input that is added records it. A
    # duplicate origin is not added, so it records none
    if (!is_source_recorded(origin) && is.null(get_graph_file_manifest()$commit)) {
        .graph_file_manifest$commit <<- get_git_head_commit()
    }

    record_source(source_entry)
}

# Register a census input (the P3 and P4 tables, a TIGER shapefile folder).
# Location and census year are enough to get it again, so it is not uploaded.
# The script declares it, because git cannot tell that an input is census data:
# some counties' tables are in git and others are not.
#
# role, source_file: as in add_source_to_graph_file_manifest
# location: the location the census data covers (e.g. "Monongalia_County_WV")
# census_year: one whole number (e.g. 2020)
add_census_source_to_graph_file_manifest <- function(role, source_file, location, census_year) {
    origin <- get_source_origin(role, source_file)
    if (!is.numeric(census_year) || length(census_year) != 1 || !is.finite(census_year) ||
            census_year != round(census_year)) {
        stop(paste0("cannot record census source ", origin, " -- census_year must be one ",
                    "whole number, got ", paste(deparse(census_year), collapse = "")))
    }

    # An integer, so that the manifest has 2020 and not 2020.0
    record_source(list(role = role, origin = origin, kind = "census",
                       location = location, census_year = as.integer(census_year)))
}

# Stops on a deliverable name that is not in KNOWN_DELIVERABLES
check_known_deliverable <- function(deliverable) {
    # Type first: %in% also matches a factor, which would name the folder by its code
    is_known <- is.character(deliverable) && length(deliverable) == 1 && !is.na(deliverable) &&
        deliverable %in% KNOWN_DELIVERABLES
    if (!is_known) {
        stop(paste0("Invalid CLOUD_STORAGE_DELIVERABLE '", paste(deliverable, collapse = ", "),
                    "'; use one of these as a character string: ",
                    paste(KNOWN_DELIVERABLES, collapse = ", "),
                    ". A new deliverable adds its name to KNOWN_DELIVERABLES in storage.R"))
    }
}

# Sets the deliverable folder for a script. The name is checked here, in the
# run's first second, not only at the upload after every map and CSV is built.
# It cannot unset the value: assign NULL to CLOUD_STORAGE_DELIVERABLE for that.
set_cloud_storage_deliverable <- function(deliverable) {
    check_known_deliverable(deliverable)
    CLOUD_STORAGE_DELIVERABLE <<- deliverable
}

# Gives this session a Google token before the first upload. Nothing else in
# storage.R authenticates. In an interactive session googleAuthR falls back to
# gar_auth(), which reuses a cached token or opens a browser. A non-interactive
# Rscript run, the normal case in the dev container, has neither and fails at
# the first gcs_upload() with "No authorization yet in this session!". The
# token comes from the application-default credentials file named by
# GOOGLE_APPLICATION_CREDENTIALS, written by `gcloud auth application-default
# login` run inside the dev container (gcloud state lives in a named volume,
# not on the host). The scope must stay cloud-platform: for a user credentials
# file gargle returns NULL for any other scope. A session that already holds a
# token keeps it.
authenticate_cloud_storage <- function() {
    if (googleAuthR::gar_has_token()) {
        return(invisible(FALSE))
    }
    token <- gargle::credentials_app_default(
        scopes = "https://www.googleapis.com/auth/cloud-platform"
    )
    if (is.null(token)) {
        stop(paste0("No Google credentials found. Run `gcloud auth application-default login ",
                    "--no-launch-browser` inside the dev container, or point ",
                    "GOOGLE_APPLICATION_CREDENTIALS at a credentials file."))
    }
    googleAuthR::gar_auth(token = token)
    invisible(TRUE)
}

# Uploads all files in the manifest to Google Cloud Storage, under
# STORAGE_BASE_DIR / CLOUD_STORAGE_ANALYSIS_NAME / [CLOUD_STORAGE_DELIVERABLE /] <datestamp>.
# Outputs, sources and the manifest all share that one path.
upload_graph_files_to_cloud_storage <- function() {
    manifest = get_graph_file_manifest()
    if (length(manifest$graph_files) < 1) {
        stop("No files to upload to cloud storage")
    }

    if (is.null(STORAGE_BASE_DIR) || nchar(STORAGE_BASE_DIR) == 0) {
        stop("STORAGE_BASE_DIR is not set; set it in the analysis script or config")
    }

    if (is.null(STORAGE_BUCKET) || nchar(STORAGE_BUCKET) == 0) {
        stop("Invalid STORAGE_BUCKET")
    }

    if (is.null(CLOUD_STORAGE_ANALYSIS_NAME) || nchar(CLOUD_STORAGE_ANALYSIS_NAME) == 0) {
        stop("Invalid CLOUD_STORAGE_ANALYSIS_NAME")
    }

    # The deliverable folder is optional. A script can assign the constant
    # directly, past set_cloud_storage_deliverable(), so check it here too
    has_deliverable <- !(is.null(CLOUD_STORAGE_DELIVERABLE) ||
                             identical(CLOUD_STORAGE_DELIVERABLE, ""))
    if (has_deliverable) {
        check_known_deliverable(CLOUD_STORAGE_DELIVERABLE)
    }

    manifest$analysis_name <- CLOUD_STORAGE_ANALYSIS_NAME
    # Assigning NULL removes the field, so an unset deliverable is left out, and
    # so is the commit when no input is in git
    manifest$deliverable <- if (has_deliverable) CLOUD_STORAGE_DELIVERABLE else NULL
    if (is.null(manifest$commit)) {
        manifest$commit <- NULL
    }

    date_stamp = format(manifest$created_at, "%Y%m%d-%H%M%S")
    # c() drops the deliverable part when it is unset
    cloud_storage_path_parts <- c(STORAGE_BASE_DIR, CLOUD_STORAGE_ANALYSIS_NAME,
                                  if (has_deliverable) CLOUD_STORAGE_DELIVERABLE, date_stamp)
    cloud_storage_base_path <- paste(cloud_storage_path_parts, collapse="/")

    # Identify the local folder to upload the manifest's files from.
    local_tree <- file.path(here(), manifest$output_tree)

    local_file_paths <- file.path(local_tree, manifest$graph_files)
    source_file_paths <- vapply(
        manifest$sources, function(source_entry) file.path(here(), source_entry$origin), character(1)
    )

    # Check every file, outputs and sources, before uploading any, avoiding a partial upload
    missing_files <- c(local_file_paths[!file.exists(local_file_paths)],
                       source_file_paths[!file.exists(source_file_paths)])
    if (length(missing_files) > 0) {
        stop(paste0("upload_graph_files_to_cloud_storage cannot find files: ",
                    paste(missing_files, collapse = ", ")))
    }

    # The inputs were read at the recorded commit, so stop if the checkout moved
    if (!is.null(manifest$commit)) {
        head_commit <- get_git_head_commit()
        if (!identical(head_commit, manifest$commit)) {
            stop(paste0("the checkout moved during the run: the inputs were recorded at commit ",
                        manifest$commit, " and the checkout is now at ", head_commit,
                        ". Run the analysis again"))
        }
    }

    # Authenticate once, only after every file is known to exist
    authenticate_cloud_storage()

    # Upload each graph file found in the manifest
    for (graph_file in manifest$graph_files) {
        local_file_path <- file.path(local_tree, graph_file)
        cloud_storage_file_name <- paste(cloud_storage_base_path, graph_file, sep="/")
        print(paste0("Uploading file ", local_file_path, " -> ", STORAGE_BUCKET, ":", cloud_storage_file_name))
        gcs_upload(file=local_file_path, bucket=STORAGE_BUCKET, name=cloud_storage_file_name, predefinedAcl=STORAGE_PREDEFINED_ACL)
    }

    # Upload the inputs that are neither in git nor census data
    for (source_entry in Filter(function(entry) identical(entry$kind, "upload"), manifest$sources)) {
        local_file_path <- file.path(here(), source_entry$origin)
        cloud_storage_file_name <- paste(cloud_storage_base_path, source_entry$object_name, sep="/")
        print(paste0("Uploading file ", local_file_path, " -> ", STORAGE_BUCKET, ":", cloud_storage_file_name))
        gcs_upload(file=local_file_path, bucket=STORAGE_BUCKET, name=cloud_storage_file_name, predefinedAcl=STORAGE_PREDEFINED_ACL)
    }

    # Upload the manifest of this analysis to cloud storage
    manifest_copy <- manifest
    manifest_copy$created_at <- format(manifest_copy$created_at, "%Y-%m-%d %H:%M:%S UTC")
    # true and false; as.yaml() writes yes and no by default
    manifest_yaml <- as.yaml(manifest_copy, handlers = list(logical = yaml::verbatim_logical))
    temp_file <- tempfile()
    writeLines(manifest_yaml, temp_file)
    cloud_storage_manifest_file_name = paste(cloud_storage_base_path, ANALYSIS_MANIFEST, sep="/")
    gcs_upload(file=temp_file, bucket=STORAGE_BUCKET, name=cloud_storage_manifest_file_name, predefinedAcl=STORAGE_PREDEFINED_ACL)

    # Return the manifest instance
    manifest
}