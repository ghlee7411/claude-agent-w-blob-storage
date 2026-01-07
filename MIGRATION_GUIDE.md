# Blob Storage 마이그레이션 가이드

이 문서는 파일 시스템 기반 스토리지에서 클라우드 Blob Storage로 마이그레이션하는 방법을 설명합니다.

## 아키텍처 설계

현재 시스템은 스토리지 계층이 추상화되어 있어, 향후 blob storage로 쉽게 전환할 수 있습니다.

### 현재 구조

```
Agent (agent.py)
    ↓
Storage Tools (storage_tools.py)
    ↓
File System (./storage/)
```

### 향후 구조

```
Agent (agent.py)
    ↓
Storage Tools (storage_tools.py or blob_storage_tools.py)
    ↓
Blob Storage (Azure/AWS/GCP)
```

## 마이그레이션 단계

### 1단계: Blob Storage 클래스 구현

`blob_storage_tools.py` 파일을 생성하여 `FileSystemStorage`와 동일한 인터페이스를 구현합니다.

#### Azure Blob Storage 예시

```python
from azure.storage.blob import BlobServiceClient, BlobClient
from typing import Dict, Any
import json

class AzureBlobStorage:
    def __init__(self, connection_string: str, container_name: str = "knowledge-base"):
        """
        Initialize Azure Blob Storage
        
        Args:
            connection_string: Azure Storage connection string
            container_name: Container name for storing files
        """
        self.blob_service_client = BlobServiceClient.from_connection_string(connection_string)
        self.container_name = container_name
        
        # Create container if it doesn't exist
        try:
            self.container_client = self.blob_service_client.get_container_client(container_name)
            self.container_client.get_container_properties()
        except:
            self.container_client = self.blob_service_client.create_container(container_name)
    
    def read_file(self, file_path: str) -> Dict[str, Any]:
        """Read content from a blob"""
        try:
            blob_client = self.container_client.get_blob_client(file_path)
            
            if not blob_client.exists():
                return {
                    "success": False,
                    "error": f"File not found: {file_path}",
                    "content": None
                }
            
            content = blob_client.download_blob().readall().decode('utf-8')
            
            return {
                "success": True,
                "content": content,
                "file_path": file_path,
                "size": len(content)
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "content": None
            }
    
    def write_file(self, file_path: str, content: str, mode: str = "w") -> Dict[str, Any]:
        """Write content to a blob"""
        try:
            blob_client = self.container_client.get_blob_client(file_path)
            
            # Handle append mode
            if mode == "a" and blob_client.exists():
                existing_content = blob_client.download_blob().readall().decode('utf-8')
                content = existing_content + content
            
            # Upload blob
            blob_client.upload_blob(content, overwrite=True)
            
            return {
                "success": True,
                "message": f"Successfully wrote to {file_path}",
                "file_path": file_path,
                "size": len(content)
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    def list_files(self, directory: str = "", pattern: str = "*") -> Dict[str, Any]:
        """List blobs in a directory"""
        try:
            prefix = directory if directory else None
            blobs = self.container_client.list_blobs(name_starts_with=prefix)
            
            files = []
            for blob in blobs:
                # Simple pattern matching (can be enhanced)
                if pattern == "*" or blob.name.endswith(pattern.replace("*", "")):
                    files.append({
                        "path": blob.name,
                        "name": blob.name.split('/')[-1],
                        "size": blob.size
                    })
            
            return {
                "success": True,
                "files": files,
                "count": len(files)
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "files": []
            }
    
    def delete_file(self, file_path: str) -> Dict[str, Any]:
        """Delete a blob"""
        try:
            blob_client = self.container_client.get_blob_client(file_path)
            
            if not blob_client.exists():
                return {
                    "success": False,
                    "error": f"File not found: {file_path}"
                }
            
            blob_client.delete_blob()
            
            return {
                "success": True,
                "message": f"Successfully deleted {file_path}"
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    def search_files(self, search_text: str, directory: str = "", file_pattern: str = "*") -> Dict[str, Any]:
        """Search for blobs containing specific text"""
        try:
            prefix = directory if directory else None
            blobs = self.container_client.list_blobs(name_starts_with=prefix)
            
            matches = []
            for blob in blobs:
                # Pattern matching
                if file_pattern != "*" and not blob.name.endswith(file_pattern.replace("*", "")):
                    continue
                
                try:
                    blob_client = self.container_client.get_blob_client(blob.name)
                    content = blob_client.download_blob().readall().decode('utf-8')
                    
                    if search_text.lower() in content.lower():
                        matching_lines = [
                            (i + 1, line.strip())
                            for i, line in enumerate(content.split('\n'))
                            if search_text.lower() in line.lower()
                        ]
                        matches.append({
                            "path": blob.name,
                            "name": blob.name.split('/')[-1],
                            "matching_lines": matching_lines[:5]
                        })
                except Exception:
                    continue
            
            return {
                "success": True,
                "matches": matches,
                "count": len(matches),
                "search_text": search_text
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "matches": []
            }
```

#### AWS S3 예시

```python
import boto3
from typing import Dict, Any

class S3Storage:
    def __init__(self, bucket_name: str, aws_access_key_id: str = None, 
                 aws_secret_access_key: str = None, region_name: str = 'us-east-1'):
        """
        Initialize AWS S3 Storage
        
        Args:
            bucket_name: S3 bucket name
            aws_access_key_id: AWS access key (optional if using IAM roles)
            aws_secret_access_key: AWS secret key (optional if using IAM roles)
            region_name: AWS region
        """
        self.bucket_name = bucket_name
        
        if aws_access_key_id and aws_secret_access_key:
            self.s3_client = boto3.client(
                's3',
                aws_access_key_id=aws_access_key_id,
                aws_secret_access_key=aws_secret_access_key,
                region_name=region_name
            )
        else:
            # Use IAM role credentials
            self.s3_client = boto3.client('s3', region_name=region_name)
        
        # Ensure bucket exists
        try:
            self.s3_client.head_bucket(Bucket=bucket_name)
        except:
            self.s3_client.create_bucket(Bucket=bucket_name)
    
    def read_file(self, file_path: str) -> Dict[str, Any]:
        """Read content from S3"""
        try:
            response = self.s3_client.get_object(Bucket=self.bucket_name, Key=file_path)
            content = response['Body'].read().decode('utf-8')
            
            return {
                "success": True,
                "content": content,
                "file_path": file_path,
                "size": len(content)
            }
        except self.s3_client.exceptions.NoSuchKey:
            return {
                "success": False,
                "error": f"File not found: {file_path}",
                "content": None
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "content": None
            }
    
    # ... 나머지 메서드는 Azure와 유사하게 구현
```

### 2단계: Agent 클래스 수정

`agent.py`에서 스토리지 백엔드를 선택할 수 있도록 수정:

```python
from storage_tools import FileSystemStorage
from blob_storage_tools import AzureBlobStorage, S3Storage

class KnowledgeBaseAgent:
    def __init__(self, api_key: str = None, storage_type: str = "filesystem", 
                 storage_config: Dict[str, Any] = None, model: str = "claude-3-5-sonnet-20241022"):
        """
        Initialize the Knowledge Base Agent
        
        Args:
            api_key: Anthropic API key
            storage_type: Type of storage - "filesystem", "azure", "s3"
            storage_config: Configuration for the storage backend
            model: Claude model to use
        """
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError("API key must be provided")
        
        self.client = Anthropic(api_key=self.api_key)
        
        # Initialize storage based on type
        if storage_type == "filesystem":
            storage_path = storage_config.get("path", "./storage") if storage_config else "./storage"
            self.storage = FileSystemStorage(storage_path)
        elif storage_type == "azure":
            self.storage = AzureBlobStorage(
                storage_config["connection_string"],
                storage_config.get("container_name", "knowledge-base")
            )
        elif storage_type == "s3":
            self.storage = S3Storage(
                storage_config["bucket_name"],
                storage_config.get("aws_access_key_id"),
                storage_config.get("aws_secret_access_key"),
                storage_config.get("region_name", "us-east-1")
            )
        else:
            raise ValueError(f"Unknown storage type: {storage_type}")
        
        self.model = model
        self.tools = get_storage_tools()
```

### 3단계: 환경 변수 설정

`.env` 파일을 사용하여 설정 관리:

```bash
# Anthropic API
ANTHROPIC_API_KEY=your-anthropic-key

# Storage Configuration
STORAGE_TYPE=azure  # or "filesystem" or "s3"

# Azure Blob Storage
AZURE_STORAGE_CONNECTION_STRING=your-connection-string
AZURE_CONTAINER_NAME=knowledge-base

# AWS S3
AWS_BUCKET_NAME=your-bucket-name
AWS_ACCESS_KEY_ID=your-access-key
AWS_SECRET_ACCESS_KEY=your-secret-key
AWS_REGION=us-east-1
```

### 4단계: 데이터 마이그레이션 스크립트

기존 파일 시스템 데이터를 blob storage로 마이그레이션:

```python
import os
from storage_tools import FileSystemStorage
from blob_storage_tools import AzureBlobStorage

def migrate_to_blob_storage(
    source_path: str = "./storage",
    connection_string: str = None,
    container_name: str = "knowledge-base"
):
    """Migrate data from file system to Azure Blob Storage"""
    
    # Initialize both storage systems
    fs_storage = FileSystemStorage(source_path)
    blob_storage = AzureBlobStorage(connection_string, container_name)
    
    # List all files
    result = fs_storage.list_files(directory="", pattern="**/*")
    
    if not result["success"]:
        print(f"Error listing files: {result['error']}")
        return
    
    # Migrate each file
    total = len(result["files"])
    for i, file_info in enumerate(result["files"], 1):
        file_path = file_info["path"]
        print(f"Migrating {i}/{total}: {file_path}")
        
        # Read from file system
        read_result = fs_storage.read_file(file_path)
        if not read_result["success"]:
            print(f"  Error reading: {read_result['error']}")
            continue
        
        # Write to blob storage
        write_result = blob_storage.write_file(file_path, read_result["content"])
        if write_result["success"]:
            print(f"  ✓ Migrated successfully")
        else:
            print(f"  ✗ Error writing: {write_result['error']}")
    
    print(f"\nMigration complete: {total} files processed")

if __name__ == "__main__":
    connection_string = os.environ.get("AZURE_STORAGE_CONNECTION_STRING")
    if not connection_string:
        print("Error: AZURE_STORAGE_CONNECTION_STRING not set")
        exit(1)
    
    migrate_to_blob_storage(connection_string=connection_string)
```

## 동시성 및 다중 에이전트 지원

### Blob Storage의 장점

1. **동시성**: 여러 에이전트가 동시에 읽기/쓰기 가능
2. **확장성**: 무제한 스토리지 용량
3. **가용성**: 높은 가용성과 내구성
4. **지역 분산**: 여러 지역에서 액세스 가능

### 동시성 처리 전략

#### 낙관적 동시성 제어

```python
def write_file_with_etag(self, file_path: str, content: str, etag: str = None) -> Dict[str, Any]:
    """Write file with optimistic concurrency control using ETag"""
    try:
        blob_client = self.container_client.get_blob_client(file_path)
        
        # Set condition to match ETag if provided
        if etag:
            blob_client.upload_blob(content, overwrite=True, etag=etag, match_condition=MatchConditions.IfNotModified)
        else:
            blob_client.upload_blob(content, overwrite=True)
        
        # Return new ETag
        properties = blob_client.get_blob_properties()
        return {
            "success": True,
            "message": f"Successfully wrote to {file_path}",
            "etag": properties.etag
        }
    except ResourceModifiedError:
        return {
            "success": False,
            "error": "File was modified by another agent. Please retry."
        }
```

#### 리스 기반 잠금

```python
from azure.storage.blob import BlobLeaseClient

def acquire_lock(self, file_path: str, timeout: int = 60) -> str:
    """Acquire a lease lock on a blob"""
    blob_client = self.container_client.get_blob_client(file_path)
    lease_client = BlobLeaseClient(blob_client)
    return lease_client.acquire(lease_duration=timeout)

def release_lock(self, file_path: str, lease_id: str):
    """Release a lease lock"""
    blob_client = self.container_client.get_blob_client(file_path)
    lease_client = BlobLeaseClient(blob_client, lease_id=lease_id)
    lease_client.release()
```

## 성능 최적화

### 캐싱 전략

```python
from functools import lru_cache
import time

class CachedBlobStorage(AzureBlobStorage):
    def __init__(self, *args, cache_ttl: int = 300, **kwargs):
        super().__init__(*args, **kwargs)
        self.cache_ttl = cache_ttl
        self._cache = {}
    
    def read_file(self, file_path: str) -> Dict[str, Any]:
        """Read with caching"""
        now = time.time()
        
        # Check cache
        if file_path in self._cache:
            cached_data, cached_time = self._cache[file_path]
            if now - cached_time < self.cache_ttl:
                return cached_data
        
        # Read from blob storage
        result = super().read_file(file_path)
        
        # Update cache
        if result["success"]:
            self._cache[file_path] = (result, now)
        
        return result
```

### 배치 작업

```python
def batch_read_files(self, file_paths: List[str]) -> List[Dict[str, Any]]:
    """Read multiple files in parallel"""
    from concurrent.futures import ThreadPoolExecutor
    
    with ThreadPoolExecutor(max_workers=10) as executor:
        results = list(executor.map(self.read_file, file_paths))
    
    return results
```

## 모니터링 및 로깅

```python
import logging
from datetime import datetime

class MonitoredBlobStorage(AzureBlobStorage):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.logger = logging.getLogger(__name__)
    
    def read_file(self, file_path: str) -> Dict[str, Any]:
        start_time = datetime.now()
        result = super().read_file(file_path)
        duration = (datetime.now() - start_time).total_seconds()
        
        self.logger.info(f"READ {file_path}: {result['success']} ({duration:.3f}s)")
        return result
```

## 비용 최적화

1. **스토리지 티어**: 자주 액세스하지 않는 데이터는 Cool/Archive 티어로 이동
2. **압축**: 큰 텍스트 파일은 압축하여 저장
3. **중복 제거**: 동일한 내용의 파일은 한 번만 저장
4. **수명 주기 정책**: 오래된 파일 자동 삭제 또는 아카이브

## 체크리스트

마이그레이션 전 확인사항:

- [ ] Blob storage 계정 생성
- [ ] 연결 문자열/자격 증명 획득
- [ ] 네트워크 연결 확인
- [ ] 백업 생성
- [ ] 마이그레이션 스크립트 테스트
- [ ] 동시성 테스트
- [ ] 성능 벤치마크
- [ ] 비용 예측
- [ ] 모니터링 설정
- [ ] 롤백 계획 수립