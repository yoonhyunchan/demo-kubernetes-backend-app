from fastapi import FastAPI, Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import boto3
from botocore.exceptions import ClientError
from datetime import datetime
import jwt
import os

app = FastAPI(title="RDS Service")

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
    rds_client = boto3.client(
        'rds',
        region_name=AWS_REGION,
        aws_access_key_id=aws_access_key,
        aws_secret_access_key=aws_secret_key
    )
else:
    rds_client = boto3.client('rds', region_name=AWS_REGION)


class QueryRequest(BaseModel):
    query: str


def verify_token(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


@app.get("/api/rds/instances")
async def list_instances(user=Depends(verify_token)):
    try:
        response = rds_client.describe_db_instances()
        instances = []
        for db in response['DBInstances']:
            instances.append({
                "id": db['DBInstanceIdentifier'],
                "engine": db['Engine'],
                "status": db['DBInstanceStatus'],
                "endpoint": db.get('Endpoint', {}).get('Address', 'N/A')
            })
        return {"instances": instances}
    except ClientError as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/rds/instances/{instance_id}/test")
async def test_connection(instance_id: str, user=Depends(verify_token)):
    try:
        response = rds_client.describe_db_instances(DBInstanceIdentifier=instance_id)
        if response['DBInstances']:
            db = response['DBInstances'][0]
            if db['DBInstanceStatus'] == 'available':
                return {"status": "success", "message": "Connection available"}
        return {"status": "error", "message": "Instance not available"}
    except ClientError as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/rds/instances/{instance_id}/query")
async def execute_query(instance_id: str, request: QueryRequest, user=Depends(verify_token)):
    # 실제 구현에서는 RDS Data API 또는 직접 연결 필요
    return {
        "status": "success",
        "rows": [{"id": 1, "name": "Sample Data"}],
        "query": request.query
    }


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "rds-service",
        "timestamp": datetime.utcnow().isoformat()
    }


@app.get("/")
async def root():
    return {"message": "RDS Service", "version": "1.0.0"}
