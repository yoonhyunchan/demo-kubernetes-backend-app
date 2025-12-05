# Backend MSA - AWS Test Platform

마이크로서비스 아키텍처로 분리된 백엔드 서비스입니다.

## 서비스 구성

| 서비스 | 포트 | 설명 |
|--------|------|------|
| auth-service | 8001 | 인증 서비스 (JWT 발급) |
| s3-service | 8002 | S3 관리 |
| ec2-service | 8003 | EC2 관리 |
| rds-service | 8004 | RDS 관리 |
| lambda-service | 8005 | Lambda 관리 |
| cloudwatch-service | 8006 | CloudWatch 로그/메트릭 |

## 아키텍처

```
Client
  ↓
auth-service (JWT 발급)
  ↓
JWT Token
  ↓
┌─────────────────────────────────────┐
│  s3-service                         │
│  ec2-service     (JWT 검증)         │
│  rds-service                        │
│  lambda-service                     │
│  cloudwatch-service                 │
└─────────────────────────────────────┘
```

## 인증 방식

- **JWT 기반 인증**
- 모든 서비스가 동일한 `SECRET_KEY` 공유
- auth-service에서 토큰 발급
- 각 서비스에서 독립적으로 JWT 검증

## 설치 및 실행

### 1. 개별 서비스 빌드

```bash
# auth-service
cd auth-service
docker build -t auth-service:latest .

# s3-service
cd s3-service
docker build -t s3-service:latest .

# 나머지 서비스도 동일하게...
```

### 2. 컨테이너 실행 (환경변수 주입)

```bash
# auth-service
docker run -d \
  --name auth-service \
  -p 8000:8000 \
  -e SECRET_KEY=your-secret-key \
  -e ALLOWED_ORIGINS=http://localhost:3000,https://www.yooniquespace.cloud \
  auth-service:latest

# s3-service
docker run -d \
  --name s3-service \
  -p 8002:8000 \
  -e SECRET_KEY=your-secret-key \
  -e AWS_ACCESS_KEY_ID=your-key \
  -e AWS_SECRET_ACCESS_KEY=your-secret \
  -e AWS_DEFAULT_REGION=ap-northeast-2 \
  -e ALLOWED_ORIGINS=http://localhost:3000,https://www.yooniquespace.cloud \
  s3-service:latest
```

### 3. Health Check 확인

```bash
curl http://localhost:8001/health  # auth-service
curl http://localhost:8002/health  # s3-service
curl http://localhost:8003/health  # ec2-service
curl http://localhost:8004/health  # rds-service
curl http://localhost:8005/health  # lambda-service
curl http://localhost:8006/health  # cloudwatch-service
```

## API 사용 예시

### 1. 로그인

```bash
curl -X POST http://localhost:8001/api/auth/login \
  -d "username=admin&password=admin"

# 응답
{
  "access_token": "eyJhbGc...",
  "token_type": "bearer"
}
```

### 2. S3 버킷 조회

```bash
curl http://localhost:8002/api/s3/buckets \
  -H "Authorization: Bearer eyJhbGc..."
```

### 3. EC2 인스턴스 조회

```bash
curl http://localhost:8003/api/ec2/instances \
  -H "Authorization: Bearer eyJhbGc..."
```

## 개별 서비스 실행 (로컬 개발용)

```bash
# auth-service
cd auth-service
pip install -r requirements.txt
export SECRET_KEY=your-secret-key
uvicorn main:app --host 0.0.0.0 --port 8000

# s3-service
cd s3-service
pip install -r requirements.txt
export SECRET_KEY=your-secret-key
export AWS_ACCESS_KEY_ID=your-key
export AWS_SECRET_ACCESS_KEY=your-secret
export AWS_DEFAULT_REGION=ap-northeast-2
uvicorn main:app --host 0.0.0.0 --port 8000

# 개발 시 자동 리로드
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

## Istio 마이그레이션 준비

현재는 각 서비스에서 JWT를 검증하지만, 나중에 Istio 도입 시:

1. 각 서비스의 `verify_token` 함수 제거
2. Istio RequestAuthentication 설정 추가
3. 서비스 코드에서 헤더로 사용자 정보 받기

```python
# Istio 도입 후
@app.get("/api/s3/buckets")
async def list_buckets(x_forwarded_user: str = Header(None)):
    # Istio가 이미 검증 완료
    return {"buckets": [...]}
```

## 트러블슈팅

### JWT 검증 실패

- 모든 서비스의 `SECRET_KEY`가 동일한지 확인
- 토큰 만료 시간 확인 (30분)

### AWS 연결 실패

```bash
# 자격증명 확인
docker exec s3-service env | grep AWS
```

### Health Check 실패

```bash
# 컨테이너 상태 확인
docker ps

# 로그 확인
docker logs s3-service
```

## 서비스 중지

```bash
# 개별 서비스 중지
docker stop auth-service s3-service ec2-service rds-service lambda-service cloudwatch-service

# 컨테이너 삭제
docker rm auth-service s3-service ec2-service rds-service lambda-service cloudwatch-service
```

## Kubernetes 배포 예시

```yaml
# auth-service-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: auth-service
spec:
  replicas: 2
  selector:
    matchLabels:
      app: auth-service
  template:
    metadata:
      labels:
        app: auth-service
    spec:
      containers:
      - name: auth-service
        image: auth-service:latest
        ports:
        - containerPort: 8000
        env:
        - name: SECRET_KEY
          valueFrom:
            secretKeyRef:
              name: jwt-secret
              key: secret-key
        - name: PORT
          value: "8000"
        - name: ALLOWED_ORIGINS
          value: "http://localhost:3000,https://www.yooniquespace.cloud"
---
apiVersion: v1
kind: Service
metadata:
  name: auth-service
spec:
  selector:
    app: auth-service
  ports:
  - port: 8000
    targetPort: 8000
```

## 프로덕션 배포

각 서비스를 독립적으로 배포 가능:
- **Kubernetes**: 위 예시 참고
- **AWS ECS**: Task Definition으로 배포
- **Docker Swarm**: Stack으로 배포

Istio 도입 시 서비스 메시로 관리 가능합니다.
