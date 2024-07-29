#/usr/bin/env bash
# Copy Credentials file to HOME/.aws/
mkdir ${HOME}/.aws
cp /credentials ${HOME}/.aws/

DRY_RUN=${DRY_RUN:-"True"}
ACTION=${ACTION:-"Apply"}

# CDKTF output options
export CI=true
export FORCE_COLOR=0
export TF_CLI_ARGS="-no-color"

CDKTF_OUT_DIR=$HOME/cdktf.out/stacks/CDKTF

if [[ $ACTION == "Apply" ]]; then
    if [[ $DRY_RUN == "True" ]]; then
        cdktf plan && \
        terraform -chdir=$CDKTF_OUT_DIR/ show -json $CDKTF_OUT_DIR/plan > $CDKTF_OUT_DIR/plan.json && \
        python3 validate_plan.py  $CDKTF_OUT_DIR/plan.json
    elif [[ $DRY_RUN == "False" ]]; then
        cdktf apply \
            --auto-approve \
            --outputs-file-include-sensitive-outputs=true \
            --outputs-file /work/output.json
    fi
elif [[ $ACTION == "Destroy" ]]; then
    if [[ $DRY_RUN == "True" ]]; then
        cdktf synth && \
        cd ${CDKTF_OUT_DIR} && \
        terraform init && \
        terraform plan -destroy
    elif [[ $DRY_RUN == "False" ]]; then
        cdktf destroy \
            --auto-approve
    fi
fi
