from fastapi import FastAPI, Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from fastapi.middleware.cors import CORSMiddleware
import boto3
from botocore.exceptions import ClientError
from datetime import datetime
import jwt
import os

app = FastAPI(title="CloudWatch Service")

# CORS 설정
allowed_origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-in-production")
ALGORITHM = "HS256"
AWS_REGION = os.getenv("AWS_DEFAULT_REGION", "ap-northeast-2")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="http://auth-service:8000/api/auth/login")

# boto3 클라이언트 생성
aws_access_key = os.getenv("AWS_ACCESS_KEY_ID")
aws_secret_key = os.getenv("AWS_SECRET_ACCESS_KEY")

if aws_access_key and aws_secret_key:
    logs_client = boto3.client(
        'logs',
        region_name=AWS_REGION,
        aws_access_key_id=aws_access_key,
        aws_secret_access_key=aws_secret_key
    )
    cloudwatch_client = boto3.client(
        'cloudwatch',
        region_name=AWS_REGION,
        aws_access_key_id=aws_access_key,
        aws_secret_access_key=aws_secret_key
    )
else:
    logs_client = boto3.client('logs', region_name=AWS_REGION)
    cloudwatch_client = boto3.client('cloudwatch', region_name=AWS_REGION)


def verify_token(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


@app.get("/api/cloudwatch/log-groups")
async def get_log_groups(user=Depends(verify_token)):
    try:
        response = logs_client.describe_log_groups()
        log_groups = [lg['logGroupName'] for lg in response['logGroups']]
        return {"log_groups": log_groups}
    except ClientError as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/cloudwatch/log-groups/{log_group_name}/streams")
async def get_log_streams(log_group_name: str, user=Depends(verify_token)):
    try:
        response = logs_client.describe_log_streams(
            logGroupName=log_group_name,
            orderBy='LastEventTime',
            descending=True,
            limit=20
        )
        log_streams = [ls['logStreamName'] for ls in response['logStreams']]
        return {"log_streams": log_streams}
    except ClientError as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/cloudwatch/log-groups/{log_group_name}/streams/{log_stream_name}/events")
async def get_log_events(log_group_name: str, log_stream_name: str, user=Depends(verify_token)):
    try:
        response = logs_client.get_log_events(
            logGroupName=log_group_name,
            logStreamName=log_stream_name,
            limit=100
        )
        events = [
            {
                "timestamp": event['timestamp'],
                "message": event['message']
            }
            for event in response['events']
        ]
        return {"events": events}
    except ClientError as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/cloudwatch/metrics/{namespace}")
async def get_metrics(namespace: str, user=Depends(verify_token)):
    try:
        response = cloudwatch_client.list_metrics(Namespace=namespace)
        metrics = [
            {
                "name": metric['MetricName'],
                "namespace": metric['Namespace']
            }
            for metric in response['Metrics']
        ]
        return {"metrics": metrics}
    except ClientError as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "cloudwatch-service",
        "timestamp": datetime.utcnow().isoformat()
    }


@app.get("/")
async def root():
    return {"message": "CloudWatch Service", "version": "1.0.0"}
