using Microsoft.AspNetCore.Mvc.RazorPages;
using Video2Timeline.Web.Models;
using Video2Timeline.Web.Services;

namespace Video2Timeline.Web.Pages;

public sealed class SettingsModel(HuggingFaceAccessService accessService) : PageModel
{
    public HuggingFaceAccessSnapshot Snapshot { get; private set; } = new();

    public string TokenSettingsUrl => "https://huggingface.co/settings/tokens";

    public string PyannoteModelUrl => "https://huggingface.co/pyannote/speaker-diarization-community-1";

    public async Task OnGetAsync(CancellationToken cancellationToken)
    {
        Snapshot = await accessService.GetSnapshotAsync(cancellationToken);
    }
}
