from fastapi import FastAPI, Depends, UploadFile, File, HTTPException
from fastapi.security import OAuth2PasswordBearer
from fastapi.middleware.cors import CORSMiddleware
import boto3
from botocore.exceptions import ClientError
from datetime import datetime
import jwt
import os

app = FastAPI(title="S3 Service")

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
    s3_client = boto3.client(
        's3',
        region_name=AWS_REGION,
        aws_access_key_id=aws_access_key,
        aws_secret_access_key=aws_secret_key
    )
else:
    s3_client = boto3.client('s3', region_name=AWS_REGION)


def verify_token(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


@app.get("/api/s3/buckets")
async def list_buckets(user=Depends(verify_token)):
    try:
        response = s3_client.list_buckets()
        buckets = [bucket['Name'] for bucket in response['Buckets']]
        return {"buckets": buckets}
    except ClientError as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/s3/buckets/{bucket_name}/objects")
async def list_objects(bucket_name: str, user=Depends(verify_token)):
    try:
        response = s3_client.list_objects_v2(Bucket=bucket_name)
        objects = []
        if 'Contents' in response:
            objects = [
                {
                    "key": obj['Key'],
                    "size": obj['Size'],
                    "last_modified": obj['LastModified'].isoformat()
                }
                for obj in response['Contents']
            ]
        return {"objects": objects}
    except ClientError as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/s3/buckets/{bucket_name}/upload")
async def upload_file(bucket_name: str, file: UploadFile = File(...), user=Depends(verify_token)):
    try:
        s3_client.upload_fileobj(file.file, bucket_name, file.filename)
        return {"message": "File uploaded successfully", "key": file.filename}
    except ClientError as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/s3/buckets/{bucket_name}/objects/{object_key}")
async def delete_object(bucket_name: str, object_key: str, user=Depends(verify_token)):
    try:
        s3_client.delete_object(Bucket=bucket_name, Key=object_key)
        return {"message": "Object deleted successfully"}
    except ClientError as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "s3-service",
        "timestamp": datetime.utcnow().isoformat()
    }


@app.get("/")
async def root():
    return {"message": "S3 Service", "version": "1.0.0"}
