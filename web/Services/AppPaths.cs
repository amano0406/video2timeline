namespace Video2Timeline.Web.Services;

public sealed class AppPaths(IConfiguration configuration)
{
    public string RuntimeDefaultsPath { get; } =
        configuration["VIDEO2TIMELINE_RUNTIME_DEFAULTS"] ?? "/app/config/runtime.defaults.json";

    public string AppDataRoot { get; } =
        configuration["VIDEO2TIMELINE_APPDATA_ROOT"] ?? "/shared/app-data";

    public string UploadsRoot { get; } =
        configuration["VIDEO2TIMELINE_UPLOADS_ROOT"] ?? "/shared/uploads";

    public string SettingsPath => Path.Combine(AppDataRoot, "settings.json");

    public string TokenPath => Path.Combine(AppDataRoot, "secrets", "huggingface.token");

    public string DownloadsRoot => Path.Combine(AppDataRoot, "downloads");
}
