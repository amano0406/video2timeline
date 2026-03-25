using Microsoft.AspNetCore.Mvc;
using Microsoft.AspNetCore.Mvc.RazorPages;
using Video2Timeline.Web.Models;
using Video2Timeline.Web.Services;

namespace Video2Timeline.Web.Pages;

public sealed class SettingsModel(
    HuggingFaceAccessService accessService,
    SettingsStore settingsStore,
    SetupStateService setupStateService,
    LanguageService languageService,
    JsonLocalizationService localizer) : PageModel
{
    public HuggingFaceAccessSnapshot Snapshot { get; private set; } = new();

    public SetupState SetupState { get; private set; } = new();

    [BindProperty]
    public string Token { get; set; } = "";

    [BindProperty]
    public bool TermsConfirmed { get; set; }

    public string? StatusMessage { get; private set; }

    public string TokenSettingsUrl => "https://huggingface.co/settings/tokens";

    public string PyannoteModelUrl => "https://huggingface.co/pyannote/speaker-diarization-community-1";

    public async Task OnGetAsync(CancellationToken cancellationToken)
    {
        await LoadPageAsync(cancellationToken);
    }

    public async Task<IActionResult> OnPostSaveAsync(CancellationToken cancellationToken)
    {
        var hasExistingToken = await settingsStore.HasTokenAsync(cancellationToken);
        if (!hasExistingToken && string.IsNullOrWhiteSpace(Token))
        {
            ModelState.AddModelError(nameof(Token), L("settings.token_required"));
        }

        if (!TermsConfirmed)
        {
            ModelState.AddModelError(nameof(TermsConfirmed), L("settings.terms_required"));
        }

        if (!ModelState.IsValid)
        {
            await LoadPageAsync(cancellationToken);
            StatusMessage = L("settings.save_blocked");
            return Page();
        }

        await settingsStore.SaveHuggingFaceAsync(
            string.IsNullOrWhiteSpace(Token) ? null : Token,
            TermsConfirmed,
            cancellationToken);

        await LoadPageAsync(cancellationToken);
        if (SetupState.IsReady)
        {
            TempData["StatusMessage"] = L("settings.save_success");
            return RedirectToPage("/Jobs/New");
        }

        StatusMessage = L("settings.save_pending");
        return Page();
    }

    private async Task LoadPageAsync(CancellationToken cancellationToken)
    {
        Snapshot = await accessService.GetSnapshotAsync(cancellationToken);
        SetupState = await setupStateService.GetAsync(cancellationToken);
        TermsConfirmed = SetupState.TermsConfirmed;
        Token = await settingsStore.ReadTokenAsync(cancellationToken) ?? "";
    }

    private string L(string key) => localizer.Get(languageService.Resolve(Request), key);
}
