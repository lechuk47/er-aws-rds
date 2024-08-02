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

# CDKTF init forces the provider re-download to calculate
# Other platform provider SHAs. USing terraform to init the configuration avoids it
# This shuold be reevaluated in the future.
# https://github.com/hashicorp/terraform-cdk/issues/3622
if [[ $ACTION == "Apply" ]]; then
    if [[ $DRY_RUN == "True" ]]; then
        cdktf synth && \
        terraform -chdir=$CDKTF_OUT_DIR init && \
        cdktf plan --skip-synth && \
        terraform -chdir=$CDKTF_OUT_DIR/ show -json $CDKTF_OUT_DIR/plan > $CDKTF_OUT_DIR/plan.json && \
        python3 validate_plan.py  $CDKTF_OUT_DIR/plan.json
    elif [[ $DRY_RUN == "False" ]]; then
        cdktf synth && \
        terraform -chdir=$CDKTF_OUT_DIR init && \
        cdktf apply \
            --skip-synth \
            --auto-approve \
            --outputs-file-include-sensitive-outputs=true \
            --outputs-file /work/output.json
    fi
elif [[ $ACTION == "Destroy" ]]; then
    if [[ $DRY_RUN == "True" ]]; then
        cdktf synth && \
        terraform -chdir=$CDKTF_OUT_DIR init && \
        terraform -chdir=$CDKTF_OUT_DIR plan -destroy
    elif [[ $DRY_RUN == "False" ]]; then
        cdktf synth && \
        terraform -chdir=$CDKTF_OUT_DIR init && \
        cdktf destroy \
            --auto-approve
    fi
fi
