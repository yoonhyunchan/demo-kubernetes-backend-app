from fastapi import FastAPI, Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from fastapi.middleware.cors import CORSMiddleware
import boto3
from botocore.exceptions import ClientError
from datetime import datetime
import jwt
import os

app = FastAPI(title="EC2 Service")

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
    ec2_client = boto3.client(
        'ec2',
        region_name=AWS_REGION,
        aws_access_key_id=aws_access_key,
        aws_secret_access_key=aws_secret_key
    )
else:
    ec2_client = boto3.client('ec2', region_name=AWS_REGION)


def verify_token(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


@app.get("/api/ec2/instances")
async def list_instances(user=Depends(verify_token)):
    try:
        response = ec2_client.describe_instances()
        instances = []
        for reservation in response['Reservations']:
            for instance in reservation['Instances']:
                instances.append({
                    "id": instance['InstanceId'],
                    "type": instance['InstanceType'],
                    "state": instance['State']['Name'],
                    "launch_time": instance['LaunchTime'].isoformat()
                })
        return {"instances": instances}
    except ClientError as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/ec2/instances/{instance_id}/start")
async def start_instance(instance_id: str, user=Depends(verify_token)):
    try:
        ec2_client.start_instances(InstanceIds=[instance_id])
        return {"message": f"Instance {instance_id} starting"}
    except ClientError as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/ec2/instances/{instance_id}/stop")
async def stop_instance(instance_id: str, user=Depends(verify_token)):
    try:
        ec2_client.stop_instances(InstanceIds=[instance_id])
        return {"message": f"Instance {instance_id} stopping"}
    except ClientError as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/ec2/instances/{instance_id}/status")
async def get_instance_status(instance_id: str, user=Depends(verify_token)):
    try:
        response = ec2_client.describe_instance_status(InstanceIds=[instance_id])
        if response['InstanceStatuses']:
            status = response['InstanceStatuses'][0]
            return {"status": status['InstanceState']['Name']}
        return {"status": "unknown"}
    except ClientError as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "ec2-service",
        "timestamp": datetime.utcnow().isoformat()
    }


@app.get("/")
async def root():
    return {"message": "EC2 Service", "version": "1.0.0"}
