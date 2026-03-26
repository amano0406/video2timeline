using Microsoft.AspNetCore.Mvc;
using Microsoft.AspNetCore.Mvc.RazorPages;
using Video2Timeline.Web.Models;
using Video2Timeline.Web.Services;

namespace Video2Timeline.Web.Pages.Jobs;

public sealed class NewModel(
    RunStore runStore,
    LanguageService languageService,
    JsonLocalizationService localizer) : PageModel
{
    [BindProperty]
    public List<IFormFile> UploadFiles { get; set; } = [];

    [BindProperty]
    public List<IFormFile> UploadDirectoryFiles { get; set; } = [];

    [TempData]
    public string? StatusMessage { get; set; }

    public Task OnGetAsync(CancellationToken cancellationToken)
    {
        return Task.CompletedTask;
    }

    public async Task<IActionResult> OnPostExecuteAsync(CancellationToken cancellationToken)
    {
        var files = UploadFiles.Concat(UploadDirectoryFiles).ToList();
        if (files.Count == 0)
        {
            ModelState.AddModelError(string.Empty, L("jobs.new.select_input"));
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

    private string L(string key) => localizer.Get(languageService.Resolve(Request), key);
}
