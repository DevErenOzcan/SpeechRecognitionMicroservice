import asyncio
import json
import os
import io

from channels.generic.websocket import AsyncWebsocketConsumer
from asgiref.sync import sync_to_async

import librosa
import numpy as np
import pandas as pd
import wave
import webrtcvad

import grpc
import grpc.aio
import transcribe_pb2_grpc
import transcribe_pb2

# VAD nesnesini oluşturup modunu ayarlıyorum
vad = webrtcvad.Vad()
vad.set_mode(2)  # 0 ile 3 arasında bir değer

sr = 48000
frame_duration = 20  # ms
frame_size = int(sr * frame_duration / 1000)



class AudioConsumer(AsyncWebsocketConsumer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.meeting_obj = None
        self.buffer = bytearray()
        self.current_segment = bytearray()
        self.is_speech_now = False
        self.not_speech_count = 0

    async def connect(self):
        from .models import Meetings
        self.meeting_obj = await Meetings.objects.acreate()
        await self.accept()

    async def receive(self, text_data=None, bytes_data=None):
        if bytes_data:
            # bytes data da 44 byte lık header var. Bu header ı atıyorum
            bytes_data = bytes_data[44:]

            # buffer da kalan data yı ekliyorum
            bytes_data = self.buffer + bytes_data

            # bytes data nın 960 a tam bölünen kısmını alıyorum. Kalan kısmı bir sonraki datada kullanmak için buffer a ekliyorum
            useable_data_len = int(len(bytes_data) // frame_size * frame_size)
            samples = bytes_data[:useable_data_len]
            self.buffer = bytes_data[useable_data_len:]

            for i in range(0, len(samples), frame_size):
                frame_data = samples[i:i + frame_size]
                is_speech = vad.is_speech(frame_data, sr)

                if is_speech:
                    if not self.is_speech_now:
                        # sessizlik 24 frame den fazlaysa ve segment 3 sn den uzunsa mevcut segmenti bölüyorum
                        if len(self.current_segment) > sr * 6:
                            if self.not_speech_count > 10:
                                from .models import Segments
                                segment_obj = await Segments.objects.acreate()

                                # son segmentin son kısmındaki sessizliğin ilk yarısını o segmentte bırakıp diğer yarısını yeni segmente ekleyeceğim
                                # böylelikle sesi tam olarak sessizliğin ortasından bölmüş oluyorum.
                                not_speech_len = self.not_speech_count * frame_size
                                not_speech_buffer = self.current_segment[-int(not_speech_len / 2):]
                                self.current_segment = self.current_segment[:-int(not_speech_len / 2)]

                                file_path = f"meetings/meet_{self.meeting_obj.id}/segment_{segment_obj.id}.wav"
                                segment_obj.path = file_path
                                await save_audio(file_path, self.current_segment)

                                print("-" * 100)
                                print(f"new segment saved: {len(self.current_segment) / (sr * 2)} sn")

                                result = await process_audio(segment_obj, self.current_segment)
                                await self.send(json.dumps(result))

                                # mevcut segmenti temizleyip yeni segmentin başına kalan yarısını ekliyorum. Böylece ses parçaları arasında kesinti olmuyor
                                self.current_segment = bytearray()
                                self.current_segment = not_speech_buffer

                        self.not_speech_count = 0

                else:
                    self.not_speech_count += 1

                self.is_speech_now = is_speech
                self.current_segment += frame_data

    async def disconnect(self, close_code):
        # file_path = f"meetings/meet_{self.meeting_id}/segment_{self.segment_count}.wav"
        # await self.save_audio(file_path, self.current_segment)

        print("-" * 100)
        print(f"new segment saved: {len(self.current_segment) / (sr * 2)} sn")
        print("Connection closed.")


async def process_audio(segment_obj, data):
    # Bellekte bir WAV dosyası oluştur
    wav_buffer = io.BytesIO()

    with wave.open(wav_buffer, 'wb') as wav_file:
        wav_file.setnchannels(1)  # Mono
        wav_file.setsampwidth(2)  # 16-bit PCM (2 byte per sample)
        wav_file.setframerate(16000)  # 16 kHz örnekleme oranı
        wav_file.writeframes(data)  # Ham sesi yaz

    wav_buffer.seek(0)

    transcription_task = asyncio.create_task(transcription_service_request(str(segment_obj.path)))

    text = await transcription_task
    print(text)




async def save_audio(filename, data):
    directory = os.path.dirname(filename)
    if directory and not os.path.exists(directory):
        os.makedirs(directory, exist_ok=True)

    with wave.open(filename, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(48000)
        wav_file.writeframes(data)



@sync_to_async
def save_segment_obj(segment_obj):
    try:
        from .models import Segments
        segment_obj.path = segment_obj.path
        segment_obj.text = segment_obj.text
        segment_obj.save()
        print(f"{segment_obj.id} id'li segment kaydedildi.")
    except Exception as e:
        print(f"Segment save error: {e}")


async def transcription_service_request(file_path):
    try:
        # WAV dosyasını oku
        with open(file_path, "rb") as f:
            audio_bytes = f.read()

        # gRPC kanalı aç
        async with grpc.aio.insecure_channel("localhost:50051") as channel:
            stub = transcribe_pb2_grpc.TranscribeStub(channel)
            request = transcribe_pb2.AudioRequest(audio_content=audio_bytes)
            response = await stub.TranscribeAudio(request)

        return response.text

    except Exception as e:
        print(f"gRPC transcription error: {e}")
        return None