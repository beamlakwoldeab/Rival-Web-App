# import statsapi
import os

# Set Google Cloud project information and initialize Vertex AI SDK

import vertexai

PROJECT_ID = "friendlyfoes"  # @param {type:"string", isTemplate: true}
# if PROJECT_ID == "friendlyfoes":
#     PROJECT_ID = str(os.environ.get("GOOGLE_CLOUD_PROJECT"))

LOCATION = os.environ.get("GOOGLE_CLOUD_REGION", "us-central1")

API_ENDPOINT = f"{LOCATION}-aiplatform.googleapis.com"

vertexai.init(project=PROJECT_ID, location=LOCATION)

# Import libraries
import json
import time

from IPython.display import HTML, Markdown, display
from google.cloud import bigquery
import googleapiclient.discovery
import googleapiclient.errors
import pandas as pd
from vertexai.batch_prediction import BatchPredictionJob
from vertexai.generative_models import GenerativeModel, Part


# Enter your YouTube data API key here
YOUTUBE_DATA_API_KEY = "AIzaSyApLGjmU3hJ4BYfMYwOlD58eAlLISSHDts"


GEMINI_PRO_MODEL_ID = "gemini-1.5-pro-002"  # @param {type:"string"}
gemini_pro_model = GenerativeModel(GEMINI_PRO_MODEL_ID)


# Create BQ client
BQ_CLIENT = bigquery.Client(project=PROJECT_ID)

# Function to run BQ query using created client and return results as data frame


def get_bq_query_results_as_df(query_text):
    bq_results_table = BQ_CLIENT.query(query_text).to_dataframe()

    return bq_results_table


# Names of BQ dataset and tables to be created/used in this notebook
BQ_DATASET = "youtube_video_analysis"  # @param {type:"string"}

BATCH_PREDICTION_REQUESTS_TABLE = (
    "video_analysis_batch_requests"  # @param {type:"string"}
)

BATCH_PREDICTION_RESULTS_TABLE = (
    "video_analysis_batch_results"  # @param {type:"string"}
)

# Create BQ dataset if it doesn't already exist
create_dataset_if_nec_query = f"""
    CREATE SCHEMA IF NOT EXISTS `{BQ_DATASET}`
    OPTIONS(
      location='{LOCATION}'
    );
    """

get_bq_query_results_as_df(create_dataset_if_nec_query)

# Function to get response from YouTube API given specific query & various other parameters

def get_yt_data_api_response_for_search_query(
    query, video_duration, max_num_days_ago, channel_id, video_order, num_video_results
):
    api_service_name = "youtube"
    api_version = "v3"
    developer_key = YOUTUBE_DATA_API_KEY

    youtube = googleapiclient.discovery.build(
        api_service_name, api_version, developerKey=developer_key
    )

    published_after_timestamp = (
        (pd.Timestamp.now() - pd.DateOffset(days=max_num_days_ago))
        .tz_localize("UTC")
        .isoformat()
    )

    # Using Search:list - https://developers.google.com/youtube/v3/docs/search/list
    yt_data_api_request = youtube.search().list(
        part="id,snippet",
        type="video",
        q=query,
        videoDuration=video_duration,
        maxResults=num_video_results,
        publishedAfter=published_after_timestamp,
        channelId=channel_id,
        order=video_order,
    )

    yt_data_api_response = yt_data_api_request.execute()

    return yt_data_api_response

# Function to convert YouTube API response into data frame w/ specific schema

def convert_yt_data_api_response_to_df(yt_data_api_response):

    # Convert API response into data frame for further analysis
    yt_data_api_response_items_df = pd.json_normalize(yt_data_api_response["items"])

    yt_data_api_response_df = yt_data_api_response_items_df.assign(
        videoURL="https://www.youtube.com/watch?v="
        + yt_data_api_response_items_df["id.videoId"]
    )[
        [
            "id.videoId",
            "videoURL",
            "snippet.title",
            "snippet.description",
            "snippet.channelId",
            "snippet.channelTitle",
            "snippet.publishedAt",
            "snippet.thumbnails.default.url",
        ]
    ].rename(
        columns={
            "id.videoId": "videoId",
            "snippet.title": "videoTitle",
            "snippet.description": "videoDescription",
            "snippet.channelId": "channelId",
            "snippet.channelTitle": "channelTitle",
            "snippet.publishedAt": "publishedAt",
            "snippet.thumbnails.default.url": "thumbnailURL",
        }
    )

    return yt_data_api_response_df

# Get summary from Gemini for each video in data frame


def get_gemini_summary_from_youtube_video_url(video_url):
    video_summary_prompt = "Summarize this video."

    # Gemini Pro for highest quality (can change to Flash if latency/cost are of concern)
    video_summary_response = gemini_pro_model.generate_content(
        [video_summary_prompt, Part.from_uri(mime_type="video/webm", uri=video_url)]
    )

    summary_text = video_summary_response.text

    return summary_text

# Get a large set of videos using YouTube Data API, prepare to analyze them in batch

# Intentionally leaving default empty to search for all videos w/in a channel
search_query = "full game"  # @param {type:"string"}

video_duration_type = (
    "long"  # @param {type:"string"}['any', 'long', 'medium', 'short']
)

published_within_last_X_days = 365  # @param {type:"integer"}

# Default value of 'UCoLrcjPV5PbUrUyXq5mjc_A' is for specific MLB channel
channel_id = "UCoLrcjPV5PbUrUyXq5mjc_A"  # @param {type:"string"}

order_criteria = "date"  # @param {type:"string"}['date', 'rating', 'relevance', 'title', 'viewCount']

# Max is 50 results on 1 API call
num_results = 5  # @param {type:"integer"}

yt_data_api_channel_results_df = get_yt_data_api_response_for_search_query(
    query=search_query,
    video_duration=video_duration_type,
    max_num_days_ago=published_within_last_X_days,
    channel_id=channel_id,
    video_order=order_criteria,
    num_video_results=num_results,
)

yt_data_api_channel_results_df = convert_yt_data_api_response_to_df(
    yt_data_api_channel_results_df
)
display(yt_data_api_channel_results_df.head())
# yt_data_api_results_df["geminiVideoSummary"] = yt_data_api_results_df["videoURL"].apply(
    # get_gemini_summary_from_youtube_video_url
# )

# display(yt_data_api_results_df[["videoTitle", "videoURL"]])

# Set up pieces (system instruction, prompt, response schema, config) for Gemini video extraction API calls

# video_extraction_system_instruction = """You are a baseball commentator and analyst that carefully looks 
#     through all frames of provided videos of full baseball games, extracting out the pieces necessary to make commentary about a game 
#     and respond to user prompts. Make sure to look through and listen to the whole video, start to finish."""


# video_extraction_prompt = """Provide a 2 paragraph summary of the key events in this video,
#     and also provide a list of each athlete, manager/coach, and team that is referenced or
#     shown. Use full names for people and teams - e.g. "Shohei Ohtani" instead of just "Ohtani"
#     and "Los Angeles Dodgers" instead of just "Dodgers." Make sure to count only those involved
#     in the actual baseball in the video, and output only 1 entity per row."""


# video_extraction_response_schema = {
#     "type": "array",
#     "items": {
#         "type": "object",
#         "properties": {
#             "summary": {"type": "string"},
#             "references": {
#                 "type": "array",
#                 "items": {
#                     "type": "object",
#                     "properties": {
#                         "entity_name": {"type": "string"},
#                         "entity_type": {
#                             "type": "string",
#                             "enum": ["athlete", "manager or coach", "team"],
#                         },
#                     },
#                 },
#             },
#         },
#     },
# }

# video_extraction_generation_config = {
#     "temperature": 0.0,
#     "max_output_tokens": 8192,
#     "response_mime_type": "application/json",
#     "response_schema": video_extraction_response_schema,
# }


# # Function to build CURL request for given YT link, using pieces above


# def get_video_extraction_curl_request_for_yt_video_link(youtube_video_link):
#     video_extraction_curl_request_dict = {
#         "system_instruction": {
#             "parts": [{"text": video_extraction_system_instruction}]
#         },
#         "contents": [
#             {
#                 "role": "user",
#                 "parts": [
#                     {"text": video_extraction_prompt},
#                     {
#                         "file_data": {
#                             "mimeType": "video/*",
#                             "fileUri": youtube_video_link,
#                         }
#                     },
#                 ],
#             }
#         ],
#         "generation_config": video_extraction_generation_config,
#     }

#     video_extraction_curl_request = json.dumps(video_extraction_curl_request_dict)

#     return video_extraction_curl_request

# # Create Gemini API CURL request for each YT video
# yt_data_api_channel_results_df["request"] = yt_data_api_channel_results_df.apply(
#     lambda row: get_video_extraction_curl_request_for_yt_video_link(row["videoURL"]),
#     axis=1,
# )

# display(yt_data_api_channel_results_df.head())

# # yt_api_results_with_bp_requests_table_load_job = BQ_CLIENT.load_table_from_dataframe(
# #     yt_data_api_channel_results_df,
# #     f"{BQ_DATASET}.{BATCH_PREDICTION_REQUESTS_TABLE}",
# #     job_config=bigquery.LoadJobConfig(write_disposition="WRITE_TRUNCATE"),
# # )

# # Wait for the load job to complete
# # yt_api_results_with_bp_requests_table_load_job.result()


# # Submit batch prediction job to analyze multiple YouTube videos at once
# # BQ URI of input table in form bq://PROJECT_ID.DATASET.TABLE
# # or Cloud Storage bucket URI
# # INPUT_URI = f"bq://{PROJECT_ID}.{BQ_DATASET}.{BATCH_PREDICTION_REQUESTS_TABLE}"

# # BQ URI of target output table in form bq://PROJECT_ID.DATASET.TABLE
# # If the table doesn't already exist, then it is created for you
# # OUTPUT_URI = f"bq://{PROJECT_ID}.{BQ_DATASET}.{BATCH_PREDICTION_RESULTS_TABLE}"

# # Pick which Gemini model to use here (default Flash)
# # MODEL_ID = GEMINI_PRO_MODEL_ID  # @param {type:"raw"} ['GEMINI_FLASH_MODEL_ID', 'GEMINI_PRO_MODEL_ID']


# # Submit batch prediction request using Vertex AI SDK
# # batch_prediction_job = BatchPredictionJob.submit(
# #     source_model=MODEL_ID, input_dataset=INPUT_URI, output_uri_prefix=OUTPUT_URI
# # )

# # # Refresh batch prediction job until complete
# # while not batch_prediction_job.has_ended:
# #     time.sleep(5)
# #     batch_prediction_job.refresh()

# # # Check if the job succeeds
# # if batch_prediction_job.has_succeeded:
# #     print("Job succeeded!")
# # else:
# #     print(f"Job failed: {batch_prediction_job.error}")

# # Pick sampling % and # of results for check of BQ results table - can leave
# # 100% & total # of results for big tables, likely sample down for larger ones

# sampling_percentage = 100  # @param {type:"number"}

# num_results = 50  # @param {type:"integer"}

# batch_prediction_results_sample_query = f"""
#     SELECT * 
#     FROM `{BQ_DATASET}.{BATCH_PREDICTION_RESULTS_TABLE}`
#     TABLESAMPLE SYSTEM ({sampling_percentage} PERCENT)
#     LIMIT {num_results}
#     """

# bq_results_table = get_bq_query_results_as_df(batch_prediction_results_sample_query)

# display(Markdown("Batch Prediction BigQuery Results Table"))

# display(bq_results_table.head())
