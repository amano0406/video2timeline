using Microsoft.AspNetCore.Mvc;
using Microsoft.AspNetCore.Mvc.RazorPages;
using Video2Timeline.Web.Models;
using Video2Timeline.Web.Services;

namespace Video2Timeline.Web.Pages.Jobs;

public sealed class IndexModel(
    RunStore runStore,
    LanguageService languageService,
    JsonLocalizationService localizer) : PageModel
{
    public IReadOnlyList<RunSummary> RecentRuns { get; private set; } = [];

    public RunSummary? ActiveRun { get; private set; }

    [TempData]
    public string? StatusMessage { get; set; }

    public async Task OnGetAsync(CancellationToken cancellationToken)
    {
        await LoadPageAsync(cancellationToken);
    }

    public async Task<IActionResult> OnPostDeleteAsync(string jobId, CancellationToken cancellationToken)
    {
        await LoadPageAsync(cancellationToken);
        try
        {
            await runStore.DeleteRunAsync(jobId, cancellationToken);
            StatusMessage = L("jobs.list.deleted");
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
        var runs = await runStore.ListRunsAsync(cancellationToken);
        ActiveRun = runs.FirstOrDefault(static run =>
            string.Equals(run.State, "pending", StringComparison.OrdinalIgnoreCase) ||
            string.Equals(run.State, "running", StringComparison.OrdinalIgnoreCase));
        RecentRuns = runs
            .Where(run => ActiveRun is null || !string.Equals(run.JobId, ActiveRun.JobId, StringComparison.OrdinalIgnoreCase))
            .ToList();
    }

    private string L(string key) => localizer.Get(languageService.Resolve(Request), key);
}
