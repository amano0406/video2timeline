using Microsoft.AspNetCore.Mvc;
using Microsoft.AspNetCore.Mvc.RazorPages;
using Video2Timeline.Web.Services;

namespace Video2Timeline.Web.Pages;

public sealed class IndexModel(SetupStateService setupStateService, RunStore runStore) : PageModel
{
    public async Task<IActionResult> OnGetAsync(CancellationToken cancellationToken)
    {
        var setupState = await setupStateService.GetAsync(cancellationToken);
        if (!setupState.IsReady)
        {
            return RedirectToPage("/Settings");
        }

        var activeRun = await runStore.GetActiveRunAsync(cancellationToken);
        if (activeRun is not null)
        {
            return RedirectToPage("/Jobs/Index");
        }

        return RedirectToPage("/Jobs/New");
    }
}
