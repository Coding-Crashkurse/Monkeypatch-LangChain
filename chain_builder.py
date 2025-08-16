from langchain_core.runnables import RunnableLambda
import time
import random


def strip_with_delay(text: str) -> str:
    sleep_duration = random.uniform(0.5, 2.5)
    print(f"[strip] Waiting for {sleep_duration:.2f} seconds...")
    time.sleep(sleep_duration)
    return text.strip()


def upper_with_delay(text: str) -> str:
    sleep_duration = random.uniform(0.5, 2.5)
    print(f"[upper] Waiting for {sleep_duration:.2f} seconds...")
    time.sleep(sleep_duration)
    return text.upper()


def punct_with_delay(text: str) -> str:
    sleep_duration = random.uniform(0.5, 2.5)
    print(f"[punct] Waiting for {sleep_duration:.2f} seconds...")
    time.sleep(sleep_duration)
    return f"{text}."


def build_pipeline():
    strip = RunnableLambda(strip_with_delay, name="strip")
    upper = RunnableLambda(upper_with_delay, name="upper")
    punct = RunnableLambda(punct_with_delay, name="punct")
    return strip | upper | punct
