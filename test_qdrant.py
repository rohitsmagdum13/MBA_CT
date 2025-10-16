from qdrant_client import QdrantClient

qdrant_client = QdrantClient(
    url="https://6cff52b1-a13c-4049-9a3e-8993feb95210.us-east-1-1.aws.cloud.qdrant.io:6333",
    api_key="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhY2Nlc3MiOiJtIn0.TdRHOh7YMp-CgFtvhcdQq01BBS3lLyacvhdDEHmKK-U",
)

print(qdrant_client.get_collections())
