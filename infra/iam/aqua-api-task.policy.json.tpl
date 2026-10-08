{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "InvokePredictorEndpoint",
      "Effect": "Allow",
      "Action": ["sagemaker:InvokeEndpoint"],
      "Resource": "arn:aws:sagemaker:${AWS_REGION}:${ACCOUNT_ID}:endpoint/${AQUA_PREDICTOR_ENDPOINT}"
    },
    {
      "Sid": "BedrockConverse",
      "Effect": "Allow",
      "Action": ["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream"],
      "Resource": ${BEDROCK_RESOURCE_ARNS_JSON}
    },
    {
      "Sid": "ReadModelArtifacts",
      "Effect": "Allow",
      "Action": ["s3:GetObject"],
      "Resource": "arn:aws:s3:::${AQUA_BUCKET}/models/*"
    }
  ]
}
