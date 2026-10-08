# 03 — AWS CLI Cheat-sheet (only what AquaAgent uses)

All commands assume `source infra/env.sh` has run (it sets `AWS_REGION`, `AQUA_BUCKET` and the names). Scripts do this for you.

## Identity / region
```bash
aws sts get-caller-identity                       # who am I, which account
aws configure list                                 # which profile/region the CLI is using
echo $AWS_REGION $AWS_PROFILE
```

## S3 (§10.2)
```bash
aws s3 ls s3://$AQUA_BUCKET/                       # top-level prefixes
aws s3 ls s3://$AQUA_BUCKET/processed/ds1/ --recursive --summarize | tail -2
aws s3 sync data/features/ds1 s3://$AQUA_BUCKET/features/ds1/
aws s3 cp s3://$AQUA_BUCKET/processed/ds1/manifest.json - | python3 -m json.tool
aws s3api get-bucket-versioning --bucket $AQUA_BUCKET
```

## ECR (§3.2)
```bash
aws ecr describe-repositories --query 'repositories[].repositoryUri'
aws ecr get-login-password | docker login --username AWS --password-stdin $ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com
aws ecr describe-images --repository-name aquaagent-api --query 'imageDetails[].imageTags'
```

## ECS (§3.2, §8.6)
```bash
aws ecs list-tasks --cluster aquaagent
aws ecs describe-services --cluster aquaagent --services aquaagent-api \
  --query 'services[0].{desired:desiredCount,running:runningCount,events:events[:3].message}'
aws ecs update-service --cluster aquaagent --service aquaagent-api --force-new-deployment
aws ecs update-service --cluster aquaagent --service aquaagent-api --desired-count 0   # park (§10.5)
aws ecs describe-tasks --cluster aquaagent --tasks <arn> --query 'tasks[0].{status:lastStatus,stop:stoppedReason,exit:containers[].exitCode}'
```

## Logs (CloudWatch)
```bash
aws logs tail /ecs/aquaagent-api --since 15m --follow
aws logs tail /ecs/aquaagent-sim --since 15m
aws logs tail /ecs/aquaagent-datagen --since 1h
aws logs tail /aws/sagemaker/TrainingJobs --log-stream-name-prefix <job-name> --since 1h
aws logs tail /aws/sagemaker/Endpoints/aquaagent-predictor --since 30m
```

## ALB / API Gateway
```bash
aws elbv2 describe-target-health --target-group-arn "$(cat infra/.state/tg_arn)" \
  --query 'TargetHealthDescriptions[].[Target.Id,TargetHealth.State,TargetHealth.Description]'
curl -s "http://$(cat infra/.state/alb_dns)/api/health"
curl -s "$(cat infra/.state/api_url)/api/health"                           # G3
aws apigatewayv2 get-apis --query 'Items[].[Name,ApiEndpoint]'
```

## SSM Parameter Store (§10.3)
```bash
aws ssm get-parameters-by-path --path /aquaagent --query 'Parameters[].[Name,Value]' --output table
aws ssm get-parameter --name /aquaagent/AQUA_API_KEY --with-decryption --query Parameter.Value --output text
aws ssm put-parameter --name /aquaagent/AQUA_PREDICTOR_VERSION --value mlp_ds1_… --type String --overwrite
```

## SageMaker (§3.2, §7.9)
```bash
aws sagemaker list-training-jobs --name-contains aquaagent --max-results 5 \
  --query 'TrainingJobSummaries[].[TrainingJobName,TrainingJobStatus]' --output table
aws sagemaker describe-training-job --training-job-name <name> --query '{s:TrainingJobStatus,why:FailureReason,out:ModelArtifacts.S3ModelArtifacts}'
aws sagemaker describe-endpoint --endpoint-name aquaagent-predictor --query EndpointStatus
aws sagemaker-runtime invoke-endpoint --endpoint-name aquaagent-predictor \
  --content-type application/json --body fileb://req.json out.json && cat out.json
aws sagemaker delete-endpoint --endpoint-name aquaagent-predictor            # STOPS THE BILL
aws service-quotas list-service-quotas --service-code sagemaker \
  --query "Quotas[?contains(QuotaName,'training job usage')].[QuotaName,Value]" --output table
```

## Bedrock (§3.2, §10.1)
```bash
aws bedrock list-foundation-models --by-provider anthropic \
  --query 'modelSummaries[].[modelId,join(`,`,inferenceTypesSupported)]' --output table
aws bedrock list-inference-profiles --query 'inferenceProfileSummaries[].inferenceProfileId'
aws bedrock-runtime converse --model-id "$AQUA_BEDROCK_MODEL_ID" \
  --messages '[{"role":"user","content":[{"text":"Reply with exactly: OK"}]}]' \
  --inference-config '{"maxTokens":10}' --query 'output.message.content[0].text'
```

## Amplify
```bash
aws amplify list-apps --query 'apps[].[name,appId,defaultDomain]'
aws amplify start-job --app-id <id> --branch-name main --job-type RELEASE
aws amplify list-jobs --app-id <id> --branch-name main --max-items 3 --query 'jobSummaries[].[jobId,status]'
```

## Cost / budget
```bash
aws budgets describe-budget --account-id $ACCOUNT_ID --budget-name aquaagent-budget \
  --query 'Budget.CalculatedSpend.ActualSpend'
aws resourcegroupstaggingapi get-resources --tag-filters Key=project,Values=aquaagent \
  --query 'ResourceTagMappingList[].ResourceARN'          # everything we tagged
```
