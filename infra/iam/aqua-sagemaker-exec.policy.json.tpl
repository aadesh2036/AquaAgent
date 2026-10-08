{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "ListBucket",
      "Effect": "Allow",
      "Action": ["s3:ListBucket"],
      "Resource": "arn:aws:s3:::${AQUA_BUCKET}"
    },
    {
      "Sid": "ReadFeaturesAndCode",
      "Effect": "Allow",
      "Action": ["s3:GetObject"],
      "Resource": [
        "arn:aws:s3:::${AQUA_BUCKET}/features/*",
        "arn:aws:s3:::${AQUA_BUCKET}/models/*",
        "arn:aws:s3:::${AQUA_BUCKET}/sagemaker/*"
      ]
    },
    {
      "Sid": "WriteModelsExperimentsAndJobOutput",
      "Effect": "Allow",
      "Action": ["s3:PutObject"],
      "Resource": [
        "arn:aws:s3:::${AQUA_BUCKET}/models/*",
        "arn:aws:s3:::${AQUA_BUCKET}/experiments/*",
        "arn:aws:s3:::${AQUA_BUCKET}/sagemaker/*"
      ]
    },
    {
      "Sid": "PullFrameworkContainers",
      "Effect": "Allow",
      "Action": ["ecr:GetAuthorizationToken", "ecr:BatchGetImage", "ecr:GetDownloadUrlForLayer",
                 "ecr:BatchCheckLayerAvailability"],
      "Resource": "*"
    },
    {
      "Sid": "Logs",
      "Effect": "Allow",
      "Action": ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents", "logs:DescribeLogStreams"],
      "Resource": "arn:aws:logs:${AWS_REGION}:${ACCOUNT_ID}:log-group:/aws/sagemaker/*"
    },
    {
      "Sid": "Metrics",
      "Effect": "Allow",
      "Action": ["cloudwatch:PutMetricData"],
      "Resource": "*"
    }
  ]
}
