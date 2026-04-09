namespace TimelineForVideo.Web.Services;

public sealed class AppPaths(IConfiguration configuration)
{
    public string RuntimeDefaultsPath { get; } =
        Read(configuration, "TIMELINEFORVIDEO_RUNTIME_DEFAULTS", "VIDEO2TIMELINE_RUNTIME_DEFAULTS", "/app/config/runtime.defaults.json");

    public string AppDataRoot { get; } =
        Read(configuration, "TIMELINEFORVIDEO_APPDATA_ROOT", "VIDEO2TIMELINE_APPDATA_ROOT", "/shared/app-data");

    public string UploadsRoot { get; } =
        Read(configuration, "TIMELINEFORVIDEO_UPLOADS_ROOT", "VIDEO2TIMELINE_UPLOADS_ROOT", "/shared/uploads");

    public string OutputsRoot { get; } =
        Read(
            configuration,
            "TIMELINEFORVIDEO_OUTPUTS_ROOT",
            "VIDEO2TIMELINE_OUTPUTS_ROOT",
            Path.Combine(Read(configuration, "TIMELINEFORVIDEO_APPDATA_ROOT", "VIDEO2TIMELINE_APPDATA_ROOT", "/shared/app-data"), "outputs"));

    public string HuggingFaceCacheRoot { get; } =
        Read(configuration, "TIMELINEFORVIDEO_HF_CACHE_ROOT", "VIDEO2TIMELINE_HF_CACHE_ROOT", "/cache/huggingface");

    public string TorchCacheRoot { get; } =
        Read(configuration, "TIMELINEFORVIDEO_TORCH_CACHE_ROOT", "VIDEO2TIMELINE_TORCH_CACHE_ROOT", "/cache/torch");

    public string SettingsPath => Path.Combine(AppDataRoot, "settings.json");

    public string TokenPath => Path.Combine(AppDataRoot, "secrets", "huggingface.token");

    public string DownloadsRoot => Path.Combine(AppDataRoot, "downloads");

    public string WorkerCapabilitiesPath => Path.Combine(AppDataRoot, "worker-capabilities.json");

    private static string Read(IConfiguration configuration, string primaryKey, string legacyKey, string fallback) =>
        configuration[primaryKey] ??
        configuration[legacyKey] ??
        fallback;
}
