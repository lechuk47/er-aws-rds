FROM quay.io/app-sre/er-base-cdktf-aws:0.0.1

USER 0

# CDKTF providers need a specific Terraform-aws-provider
# Check this URL and set both provider versions accordingly
# Here and in the requirements file.
# https://github.com/cdktf/cdktf-provider-aws/releases
# Eg: cdktf-cdktf-provider-aws-18.0.9 --> Terraform-AWS-PROVIDER 5.29.0
# 19.6.0 -> 5.37.0

ENV TF_PROVIDER_RANDOM_VERSION="3.6.2"

ENV TF_PROVIDER_RANDOM_PATH="${TF_PLUGIN_CACHE}/registry.terraform.io/hashicorp/random/${TF_PROVIDER_RANDOM_VERSION}/linux_amd64"

RUN mkdir -p ${TF_PROVIDER_RANDOM_PATH} && \
    curl -sfL https://releases.hashicorp.com/terraform-provider-random/${TF_PROVIDER_RANDOM_VERSION}/terraform-provider-random_${TF_PROVIDER_RANDOM_VERSION}_linux_amd64.zip \
    -o /tmp/package-${TF_PROVIDER_RANDOM_VERSION}.zip && \
    unzip /tmp/package-${TF_PROVIDER_RANDOM_VERSION}.zip -d ${TF_PROVIDER_RANDOM_PATH}/ && \
    rm /tmp/package-${TF_PROVIDER_RANDOM_VERSION}.zip

COPY requirements.txt ./
RUN pip3 install -r requirements.txt

COPY rds.py input.py validate_plan.py main.py cdktf.json entrypoint.sh ./
ENTRYPOINT [ "bash", "entrypoint.sh" ]
