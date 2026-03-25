using Microsoft.AspNetCore.Mvc;
using Microsoft.AspNetCore.Mvc.RazorPages;
using Video2Timeline.Web.Models;
using Video2Timeline.Web.Services;

namespace Video2Timeline.Web.Pages.Runs;

public sealed class DetailsModel(RunStore runStore) : PageModel
{
    public RunDetails? Run { get; private set; }

    public async Task<IActionResult> OnGetAsync(string id, CancellationToken cancellationToken)
    {
        Run = await runStore.GetRunDetailsAsync(id, cancellationToken);
        return Run is null ? NotFound() : Page();
    }
}
