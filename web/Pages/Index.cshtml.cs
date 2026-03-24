using Microsoft.AspNetCore.Mvc;
using Microsoft.AspNetCore.Mvc.RazorPages;
using Video2Timeline.Web.Models;
using Video2Timeline.Web.Services;

namespace Video2Timeline.Web.Pages;

public sealed class IndexModel(
    RunStore runStore,
    HuggingFaceAccessService accessService,
    LanguageService languageService,
    JsonLocalizationService localizer) : PageModel
{
    public IReadOnlyList<RunSummary> RecentRuns { get; private set; } = [];

    public RunSummary? ActiveRun { get; private set; }

    public HuggingFaceAccessSnapshot SettingsSnapshot { get; private set; } = new();

    public bool SettingsReady => string.Equals(SettingsSnapshot.AccessState, "authorized", StringComparison.OrdinalIgnoreCase);

    public string Language { get; private set; } = "ja";

    [BindProperty]
    public List<IFormFile> UploadFiles { get; set; } = [];

    [BindProperty]
    public List<IFormFile> UploadDirectoryFiles { get; set; } = [];

    public string? InfoMessage { get; private set; }

    public async Task OnGetAsync(CancellationToken cancellationToken)
    {
        await LoadPageAsync(cancellationToken);
    }

    public async Task<IActionResult> OnPostCreateJobAsync(CancellationToken cancellationToken)
    {
        await LoadPageAsync(cancellationToken);
        if (!SettingsReady)
        {
            return RedirectToPage("/Settings");
        }

        if (ActiveRun is not null)
        {
            ModelState.AddModelError(string.Empty, L("index.form.another_running"));
            return Page();
        }

        var files = UploadFiles.Concat(UploadDirectoryFiles).ToList();
        if (files.Count == 0)
        {
            ModelState.AddModelError(string.Empty, L("index.form.select_input"));
            return Page();
        }

        var uploaded = await runStore.SaveUploadsAsync(files, cancellationToken);
        var created = await runStore.CreateJobAsync(
            new CreateJobCommand
            {
                UploadedFiles = uploaded.ToList(),
            },
            cancellationToken);

        return RedirectToPage("/Runs/Details", new { id = created.JobId });
    }

    public async Task<IActionResult> OnPostDeleteAsync(string jobId, CancellationToken cancellationToken)
    {
        await LoadPageAsync(cancellationToken);
        try
        {
            await runStore.DeleteRunAsync(jobId, cancellationToken);
            return RedirectToPage();
        }
        catch (InvalidOperationException ex)
        {
            ModelState.AddModelError(string.Empty, ex.Message);
            return Page();
        }
    }

    private async Task LoadPageAsync(CancellationToken cancellationToken)
    {
        Language = languageService.Resolve(Request);
        var runs = await runStore.ListRunsAsync(cancellationToken);
        ActiveRun = runs.FirstOrDefault(static run =>
            string.Equals(run.State, "pending", StringComparison.OrdinalIgnoreCase) ||
            string.Equals(run.State, "running", StringComparison.OrdinalIgnoreCase));
        RecentRuns = runs
            .Where(run => ActiveRun is null || !string.Equals(run.JobId, ActiveRun.JobId, StringComparison.OrdinalIgnoreCase))
            .ToList();
        SettingsSnapshot = await accessService.GetSnapshotAsync(cancellationToken);
        InfoMessage = L("index.form.cache_notice");
    }

    private string L(string key) => localizer.Get(Language, key);
}
