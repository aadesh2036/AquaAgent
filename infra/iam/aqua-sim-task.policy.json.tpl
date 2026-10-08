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
      "Sid": "ReadWriteDatasetObjects",
      "Effect": "Allow",
      "Action": ["s3:GetObject", "s3:PutObject"],
      "Resource": [
        "arn:aws:s3:::${AQUA_BUCKET}/configs/*",
        "arn:aws:s3:::${AQUA_BUCKET}/raw/*",
        "arn:aws:s3:::${AQUA_BUCKET}/processed/*"
      ]
    }
  ]
}
