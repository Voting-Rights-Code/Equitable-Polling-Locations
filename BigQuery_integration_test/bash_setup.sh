#pip install virtualenv
virtualenv gcloud_env
source gloud_env/bin/activate 
gcloud_env/bin/pip install google-cloud-bigquery

gcloud auth application-default login --impersonate-service-account my-bigquery-sa@voting-rights-storage-test.iam.gserviceaccount.com