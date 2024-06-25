#pip install virtualenv
virtualenv gcloud_env
source gcloud_env/bin/activate 
gcloud_env/bin/pip install google-cloud-bigquery
gcloud_env/bin/pip install pandas
gcloud_env/bin/pip install ast
gcloud_env/bin/pip install pyarrow



#gcloud auth application-default login --impersonate-service-account my-bigquery-sa@voting-rights-storage-test.iam.gserviceaccount.com
