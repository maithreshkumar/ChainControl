FROM python:3.13-alpine
WORKDIR /agent
COPY agent.py /agent/agent.py
COPY rpc_proxy.py /agent/rpc_proxy.py
USER 65532:65532
ENTRYPOINT ["python", "/agent/agent.py"]
