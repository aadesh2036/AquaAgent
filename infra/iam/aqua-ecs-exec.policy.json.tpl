{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "ReadAquaSsmParamsForSecretsInjection",
      "Effect": "Allow",
      "Action": ["ssm:GetParameters"],
      "Resource": "arn:aws:ssm:${AWS_REGION}:${ACCOUNT_ID}:parameter${SSM_PREFIX}/*"
    },
    {
      "Sid": "DecryptDefaultSsmKey",
      "Effect": "Allow",
      "Action": ["kms:Decrypt"],
      "Resource": "*",
      "Condition": {"StringEquals": {"kms:ViaService": "ssm.${AWS_REGION}.amazonaws.com"}}
    }
  ]
}
