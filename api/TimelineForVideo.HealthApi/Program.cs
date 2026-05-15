using System.Text.Json;

var settingsPath = HealthSettings.ResolveSettingsPath();
var apiPort = HealthSettings.ReadApiPortOrDefault(settingsPath, 19500);

var builder = WebApplication.CreateBuilder(args);
if (string.IsNullOrWhiteSpace(Environment.GetEnvironmentVariable("ASPNETCORE_URLS")))
{
    builder.WebHost.UseUrls($"http://127.0.0.1:{apiPort}");
}

var app = builder.Build();

app.MapGet("/health", () =>
{
    var value = HealthSettings.IsHealthy(settingsPath) ? "true" : "false";
    return Results.Text(value, "text/plain");
});

app.Run();

internal static class HealthSettings
{
    public static string ResolveSettingsPath()
    {
        var configured = Environment.GetEnvironmentVariable("TIMELINE_FOR_VIDEO_SETTINGS_PATH");
        if (!string.IsNullOrWhiteSpace(configured))
        {
            return configured;
        }

        var workspacePath = Path.Combine("/workspace", "settings.json");
        if (File.Exists(workspacePath))
        {
            return workspacePath;
        }

        return Path.Combine(AppContext.BaseDirectory, "settings.json");
    }

    public static int ReadApiPortOrDefault(string path, int fallback)
    {
        try
        {
            using var document = JsonDocument.Parse(File.ReadAllText(path));
            if (!document.RootElement.TryGetProperty("runtime", out var runtime))
            {
                return fallback;
            }

            if (!runtime.TryGetProperty("apiPort", out var apiPort))
            {
                return fallback;
            }

            if (apiPort.ValueKind == JsonValueKind.Number && apiPort.TryGetInt32(out var port))
            {
                return IsValidPort(port) ? port : fallback;
            }

            if (apiPort.ValueKind == JsonValueKind.String && int.TryParse(apiPort.GetString(), out port))
            {
                return IsValidPort(port) ? port : fallback;
            }
        }
        catch (IOException)
        {
        }
        catch (JsonException)
        {
        }
        catch (UnauthorizedAccessException)
        {
        }

        return fallback;
    }

    public static bool IsHealthy(string path)
    {
        try
        {
            using var document = JsonDocument.Parse(File.ReadAllText(path));
            var root = document.RootElement;
            if (root.ValueKind != JsonValueKind.Object)
            {
                return false;
            }

            if (!root.TryGetProperty("schemaVersion", out var schemaVersion)
                || schemaVersion.ValueKind != JsonValueKind.Number
                || !schemaVersion.TryGetInt32(out var schema)
                || schema != 1)
            {
                return false;
            }

            if (!root.TryGetProperty("inputRoots", out var inputRoots)
                || inputRoots.ValueKind != JsonValueKind.Array
                || !inputRoots.EnumerateArray().Any(IsNonEmptyString))
            {
                return false;
            }

            if (!root.TryGetProperty("outputRoot", out var outputRoot) || !IsNonEmptyString(outputRoot))
            {
                return false;
            }

            if (root.TryGetProperty("huggingFaceToken", out var token)
                && token.ValueKind is not JsonValueKind.String and not JsonValueKind.Null)
            {
                return false;
            }

            if (root.TryGetProperty("computeMode", out var computeMode) && !IsComputeMode(computeMode))
            {
                return false;
            }

            if (root.TryGetProperty("runtime", out var runtime) && !IsRuntime(runtime))
            {
                return false;
            }

            return true;
        }
        catch (IOException)
        {
            return false;
        }
        catch (JsonException)
        {
            return false;
        }
        catch (UnauthorizedAccessException)
        {
            return false;
        }
    }

    private static bool IsRuntime(JsonElement runtime)
    {
        if (runtime.ValueKind != JsonValueKind.Object)
        {
            return false;
        }

        if (runtime.TryGetProperty("instanceName", out var instanceName)
            && instanceName.ValueKind is not JsonValueKind.String and not JsonValueKind.Null)
        {
            return false;
        }

        if (!runtime.TryGetProperty("apiPort", out var apiPort))
        {
            return true;
        }

        if (apiPort.ValueKind == JsonValueKind.Number && apiPort.TryGetInt32(out var numberPort))
        {
            return IsValidPort(numberPort);
        }

        if (apiPort.ValueKind == JsonValueKind.String && int.TryParse(apiPort.GetString(), out var stringPort))
        {
            return IsValidPort(stringPort);
        }

        return false;
    }

    private static bool IsComputeMode(JsonElement value)
    {
        if (value.ValueKind is JsonValueKind.Null or JsonValueKind.Undefined)
        {
            return true;
        }

        if (value.ValueKind != JsonValueKind.String)
        {
            return false;
        }

        var text = value.GetString();
        return string.IsNullOrWhiteSpace(text)
            || string.Equals(text, "cpu", StringComparison.OrdinalIgnoreCase)
            || string.Equals(text, "gpu", StringComparison.OrdinalIgnoreCase);
    }

    private static bool IsNonEmptyString(JsonElement value)
    {
        return value.ValueKind == JsonValueKind.String && !string.IsNullOrWhiteSpace(value.GetString());
    }

    private static bool IsValidPort(int port)
    {
        return port is >= 1 and <= 65535;
    }
}
