from fastapi import FastAPI, Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import boto3
import json
from botocore.exceptions import ClientError
from datetime import datetime
import jwt
import os

app = FastAPI(title="Lambda Service")

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
    lambda_client = boto3.client(
        'lambda',
        region_name=AWS_REGION,
        aws_access_key_id=aws_access_key,
        aws_secret_access_key=aws_secret_key
    )
    logs_client = boto3.client(
        'logs',
        region_name=AWS_REGION,
        aws_access_key_id=aws_access_key,
        aws_secret_access_key=aws_secret_key
    )
else:
    lambda_client = boto3.client('lambda', region_name=AWS_REGION)
    logs_client = boto3.client('logs', region_name=AWS_REGION)


class InvokeRequest(BaseModel):
    payload: dict


def verify_token(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


@app.get("/api/lambda/functions")
async def list_functions(user=Depends(verify_token)):
    try:
        response = lambda_client.list_functions()
        functions = []
        for func in response['Functions']:
            functions.append({
                "name": func['FunctionName'],
                "runtime": func['Runtime'],
                "last_modified": func['LastModified']
            })
        return {"functions": functions}
    except ClientError as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/lambda/functions/{function_name}/invoke")
async def invoke_function(function_name: str, request: InvokeRequest, user=Depends(verify_token)):
    try:
        response = lambda_client.invoke(
            FunctionName=function_name,
            InvocationType='RequestResponse',
            Payload=json.dumps(request.payload)
        )
        result = json.loads(response['Payload'].read())
        return {
            "status_code": response['StatusCode'],
            "result": result
        }
    except ClientError as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/lambda/functions/{function_name}/logs")
async def get_logs(function_name: str, user=Depends(verify_token)):
    try:
        log_group_name = f"/aws/lambda/{function_name}"
        response = logs_client.describe_log_streams(
            logGroupName=log_group_name,
            orderBy='LastEventTime',
            descending=True,
            limit=1
        )
        
        if response['logStreams']:
            log_stream = response['logStreams'][0]['logStreamName']
            events_response = logs_client.get_log_events(
                logGroupName=log_group_name,
                logStreamName=log_stream,
                limit=50
            )
            logs = [event['message'] for event in events_response['events']]
            return {"logs": logs}
        return {"logs": []}
    except ClientError as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "lambda-service",
        "timestamp": datetime.utcnow().isoformat()
    }


@app.get("/")
async def root():
    return {"message": "Lambda Service", "version": "1.0.0"}
