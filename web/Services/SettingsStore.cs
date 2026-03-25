using System.Text.Json;
using Video2Timeline.Web.Models;

namespace Video2Timeline.Web.Services;

public sealed class SettingsStore(AppPaths paths)
{
    private readonly JsonSerializerOptions _jsonOptions = new()
    {
        WriteIndented = true,
        PropertyNameCaseInsensitive = true,
    };

    public async Task<AppSettingsDocument> LoadAsync(CancellationToken cancellationToken = default)
    {
        if (File.Exists(paths.SettingsPath))
        {
            await using var stream = File.OpenRead(paths.SettingsPath);
            var loaded = await JsonSerializer.DeserializeAsync<AppSettingsDocument>(stream, _jsonOptions, cancellationToken);
            return Normalize(loaded ?? new AppSettingsDocument());
        }

        if (File.Exists(paths.RuntimeDefaultsPath))
        {
            await using var stream = File.OpenRead(paths.RuntimeDefaultsPath);
            var defaults = await JsonSerializer.DeserializeAsync<AppSettingsDocument>(stream, _jsonOptions, cancellationToken);
            return Normalize(defaults ?? new AppSettingsDocument());
        }

        return Normalize(new AppSettingsDocument());
    }

    public async Task SaveAsync(
        AppSettingsDocument settings,
        string? token = null,
        bool replaceToken = false,
        CancellationToken cancellationToken = default)
    {
        settings = Normalize(settings);
        Directory.CreateDirectory(Path.GetDirectoryName(paths.SettingsPath)!);
        await File.WriteAllTextAsync(
            paths.SettingsPath,
            JsonSerializer.Serialize(settings, _jsonOptions),
            cancellationToken);

        if (!replaceToken)
        {
            return;
        }

        Directory.CreateDirectory(Path.GetDirectoryName(paths.TokenPath)!);
        if (string.IsNullOrWhiteSpace(token))
        {
            if (File.Exists(paths.TokenPath))
            {
                File.Delete(paths.TokenPath);
            }

            return;
        }

        await File.WriteAllTextAsync(paths.TokenPath, token.Trim(), cancellationToken);
    }

    public async Task<bool> HasTokenAsync(CancellationToken cancellationToken = default)
    {
        if (!File.Exists(paths.TokenPath))
        {
            return false;
        }

        var value = await File.ReadAllTextAsync(paths.TokenPath, cancellationToken);
        return !string.IsNullOrWhiteSpace(value);
    }

    public async Task<string?> ReadTokenAsync(CancellationToken cancellationToken = default)
    {
        if (!File.Exists(paths.TokenPath))
        {
            return null;
        }

        var value = await File.ReadAllTextAsync(paths.TokenPath, cancellationToken);
        return string.IsNullOrWhiteSpace(value) ? null : value.Trim();
    }

    public async Task SaveHuggingFaceAsync(string? token, bool termsConfirmed, CancellationToken cancellationToken = default)
    {
        var settings = await LoadAsync(cancellationToken);
        settings.HuggingfaceTermsConfirmed = termsConfirmed;
        await SaveAsync(settings, token, replaceToken: !string.IsNullOrWhiteSpace(token), cancellationToken);
    }

    public string TermsNotice =>
        "pyannote の話者分離を使うには、Hugging Face token の保存と gated model へのアクセス承認が必要です。";

    private static AppSettingsDocument Normalize(AppSettingsDocument value)
    {
        value.InputRoots ??= [];
        value.OutputRoots ??= [];
        value.VideoExtensions ??= [];
        value.InputRoots = value.InputRoots
            .Where(static row => !string.IsNullOrWhiteSpace(row.Id) && !string.IsNullOrWhiteSpace(row.Path))
            .ToList();
        value.OutputRoots = value.OutputRoots
            .Where(static row => !string.IsNullOrWhiteSpace(row.Id) && !string.IsNullOrWhiteSpace(row.Path))
            .ToList();
        if (value.OutputRoots.Count > 1)
        {
            value.OutputRoots = [value.OutputRoots.First()];
        }

        if (value.OutputRoots.Count == 1)
        {
            value.OutputRoots[0].Id = "runs";
            value.OutputRoots[0].DisplayName = "Runs";
            value.OutputRoots[0].Enabled = true;
        }

        value.ComputeMode = value.ComputeMode?.Trim().ToLowerInvariant() switch
        {
            "gpu" => "gpu",
            _ => "cpu",
        };

        return value;
    }
}
