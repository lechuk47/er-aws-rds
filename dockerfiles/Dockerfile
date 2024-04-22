FROM quay.io/app-sre/er-base-aws-cdktf:0.0.1

USER 0

ENV TF_PLUGIN_CACHE="${HOME}/.terraform.d/plugin-cache"
ENV TF_PROVIDER_RANDOM_VERSION="3.6.0"
ENV TF_PROVIDER_RANDOM_PATH="${TF_PLUGIN_CACHE}/registry.terraform.io/hashicorp/random/${TF_PROVIDER_RANDOM_VERSION}/linux_amd64"


RUN mkdir -p ${TF_PROVIDER_RANDOM_PATH} && \
    curl -sfL https://releases.hashicorp.com/terraform-provider-random/${TF_PROVIDER_RANDOM_VERSION}/terraform-provider-random_${TF_PROVIDER_RANDOM_VERSION}_linux_amd64.zip \
    -o /tmp/package-${TF_PROVIDER_RANDOM_VERSION}.zip && \
    unzip /tmp/package-${TF_PROVIDER_RANDOM_VERSION}.zip -d ${TF_PROVIDER_RANDOM_PATH}/ && \
    rm /tmp/package-${TF_PROVIDER_RANDOM_VERSION}.zip

COPY rds.py input.py main.py cdktf.json entrypoint.sh requirements.txt ./
RUN pip3 install -r requirements.txt
ENTRYPOINT [ "bash", "entrypoint.sh" ]
