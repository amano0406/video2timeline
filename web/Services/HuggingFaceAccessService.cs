using System.Net;
using System.Net.Http.Headers;
using Video2Timeline.Web.Models;

namespace Video2Timeline.Web.Services;

public sealed class HuggingFaceAccessService(HttpClient httpClient, SettingsStore settingsStore, IConfiguration configuration)
{
    private const string PyannoteResolveUrl = "https://huggingface.co/pyannote/speaker-diarization-community-1/resolve/main/config.yaml";
    private readonly string? _overrideState = configuration["VIDEO2TIMELINE_HF_ACCESS_OVERRIDE"];

    public async Task<HuggingFaceAccessSnapshot> GetSnapshotAsync(CancellationToken cancellationToken = default)
    {
        var settings = await settingsStore.LoadAsync(cancellationToken);
        var hasToken = await settingsStore.HasTokenAsync(cancellationToken);
        var snapshot = new HuggingFaceAccessSnapshot
        {
            HasToken = hasToken,
            TermsConfirmed = settings.HuggingfaceTermsConfirmed,
        };

        if (!string.IsNullOrWhiteSpace(_overrideState))
        {
            snapshot.AccessState = _overrideState.Trim().ToLowerInvariant();
            snapshot.AccessMessage = snapshot.AccessState;
            return snapshot;
        }

        if (!hasToken)
        {
            snapshot.AccessState = "token_missing";
            snapshot.AccessMessage = "Token が未設定です。";
            return snapshot;
        }

        if (!settings.HuggingfaceTermsConfirmed)
        {
            snapshot.AccessState = "consent_pending";
            snapshot.AccessMessage = "モデル利用条件の確認が未完了です。";
            return snapshot;
        }

        var token = await settingsStore.ReadTokenAsync(cancellationToken);
        if (string.IsNullOrWhiteSpace(token))
        {
            snapshot.AccessState = "token_missing";
            snapshot.AccessMessage = "Token が未設定です。";
            return snapshot;
        }

        try
        {
            using var request = new HttpRequestMessage(HttpMethod.Get, PyannoteResolveUrl);
            request.Headers.Authorization = new AuthenticationHeaderValue("Bearer", token);
            using var response = await httpClient.SendAsync(request, HttpCompletionOption.ResponseHeadersRead, cancellationToken);

            if (response.IsSuccessStatusCode)
            {
                snapshot.AccessState = "authorized";
                snapshot.AccessMessage = "pyannote モデルへのアクセスは利用可能です。";
                return snapshot;
            }

            if (response.StatusCode is HttpStatusCode.Forbidden or HttpStatusCode.Unauthorized)
            {
                snapshot.AccessState = "unauthorized";
                snapshot.AccessMessage = "token は保存済みですが、モデル承認がまだ反映されていません。";
                return snapshot;
            }

            snapshot.AccessState = "unknown";
            snapshot.AccessMessage = $"承認状態を確認できませんでした。HTTP {(int)response.StatusCode}";
            return snapshot;
        }
        catch (Exception ex)
        {
            snapshot.AccessState = "unknown";
            snapshot.AccessMessage = $"承認状態の確認に失敗しました: {ex.Message}";
            return snapshot;
        }
    }
}
