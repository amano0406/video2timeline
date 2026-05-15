FROM mcr.microsoft.com/dotnet/sdk:10.0 AS build

WORKDIR /src
COPY api/TimelineForVideo.HealthApi/TimelineForVideo.HealthApi.csproj api/TimelineForVideo.HealthApi/
RUN dotnet restore api/TimelineForVideo.HealthApi/TimelineForVideo.HealthApi.csproj -r linux-x64

COPY api/TimelineForVideo.HealthApi/ api/TimelineForVideo.HealthApi/
RUN dotnet publish api/TimelineForVideo.HealthApi/TimelineForVideo.HealthApi.csproj \
    -c Release \
    -r linux-x64 \
    --self-contained true \
    --no-restore \
    -o /app/publish \
    /p:UseAppHost=true

FROM mcr.microsoft.com/dotnet/runtime-deps:10.0 AS runtime

ENV ASPNETCORE_URLS=http://0.0.0.0:8080
ENV TIMELINE_FOR_VIDEO_SETTINGS_PATH=/workspace/settings.json

WORKDIR /workspace
COPY --from=build /app/publish /app/health-api
RUN chmod +x /app/health-api/TimelineForVideo.HealthApi

ENTRYPOINT ["/app/health-api/TimelineForVideo.HealthApi"]
