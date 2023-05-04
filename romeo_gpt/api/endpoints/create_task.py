# romeo-gtp/romeo_gpt/api/endpoints/create_task.py

from fastapi import APIRouter, Request
from pydantic import BaseModel
from datetime import datetime

from langdetect import detect
from romeo_gpt import (
    API_KEY,
    redis_conn,
)
from romeo_gpt.utils.models.models import get_embedding
from romeo_gpt.utils.database.redis.search_index import search_index
from romeo_gpt.utils.database.redis.database import list_docs
from romeo_gpt.utils.agents.docs_agent import documents_agent
from romeo_gpt.utils.database.mongodb import db

# Access the MongoDB collection for log_data
log_data_collection = db["create-task-endpoint"]


# Define Task model with a single 'task' field
class Task(BaseModel):
    task: str


# Create FastAPI router
router = APIRouter()


# Define create_task endpoint
@router.post("/")
async def create_task(request: Request, t: Task):
    """
    Endpoint to create a task.

    :param request: HTTP request object.
    :param t: Task object containing a task string.
    :return: Dictionary containing the task and its answer.
    """

    # Get the client's IP address
    client_ip = request.client.host

    # Set the index_name using the client's IP address
    index_name = f"romeo-db-index-{client_ip}"

    # Get task from input
    task = t.task

    # Detect language of the task
    language = detect(task)

    # Get the embedding of the task
    query_vector = get_embedding(task, API_KEY)

    # List all documents in Redis
    all_documents = list_docs(redis_conn, index_name)

    # Search Redis for relevant documents
    search_results = search_index(
        redis_conn,
        index_name,
        query_vector,
        return_fields=["document_name", "text_chunks"],
    )

    # If no search results, use all documents
    if len(search_results) == 0:
        search_results = all_documents

    # Get the most relevant document
    relevant_doc = search_results[0]

    # Extract text chunks from the relevant document
    text_chunks = relevant_doc["text_chunks"]

    # Use documents_agent to generate an answer
    answer = documents_agent(language, text_chunks, task, API_KEY)

    # Prepare log_data
    log_data = {
        "question_asked": task,
        "question_embedded": query_vector.tolist(),
        "answer": answer,
        "timestamp": datetime.utcnow(),
        "client_ip": client_ip,
    }

    # Insert log_data into the MongoDB log_data collection
    log_data_collection.insert_one(log_data)

    # Return the task and its answer
    return {"task": task, "answer": answer}
