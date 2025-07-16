import grpc
from concurrent import futures
from whisperx.asr import load_model
import tempfile
import os

import transcribe_pb2
import transcribe_pb2_grpc


class TranscribeServicer(transcribe_pb2_grpc.TranscribeServicer):
    def __init__(self):
        print("Loading WhisperX model...")
        self.model = load_model("large", "cpu", compute_type="float32")
        print("Model loaded.")

    def TranscribeAudio(self, request, context):
        print("Received transcription request")
        text = self.transcribe_audio(request.audio_content)
        return transcribe_pb2.TranscribeReply(text=text)

    def transcribe_audio(self, audio_bytes: bytes, language: str = "tr") -> str:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp:
            tmp.write(audio_bytes)
            tmp_path = tmp.name

        result = self.model.transcribe(tmp_path, language=language)
        os.remove(tmp_path)
        return result["segments"][0]["text"]


def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=4))
    transcribe_pb2_grpc.add_TranscribeServicer_to_server(TranscribeServicer(), server)
    server.add_insecure_port('[::]:50051')
    server.start()
    print("WhisperX gRPC Server running on port 50051...")
    server.wait_for_termination()


if __name__ == '__main__':
    serve()
