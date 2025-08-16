from chain_builder import build_pipeline
from patcher import Patcher

if __name__ == "__main__":
    pipe = build_pipeline()
    patcher = Patcher(base_url="localhost:8000")
    # patcher.autolog("simple")
    patcher.autolog("production")
    pipe.invoke("hello")
