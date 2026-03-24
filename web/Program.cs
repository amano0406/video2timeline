using Video2Timeline.Web.Models;
using Video2Timeline.Web.Services;

var builder = WebApplication.CreateBuilder(args);

builder.Services.AddRazorPages();
builder.Services.AddSingleton<AppPaths>();
builder.Services.AddSingleton<SettingsStore>();
builder.Services.AddSingleton<ScanService>();
builder.Services.AddSingleton<RunStore>();
builder.Services.AddSingleton<LanguageService>();
builder.Services.AddSingleton<JsonLocalizationService>();
builder.Services.AddHttpClient<HuggingFaceAccessService>(client =>
{
    client.Timeout = TimeSpan.FromSeconds(10);
});
builder.Services.AddHostedService<UploadCleanupService>();

var app = builder.Build();

if (!app.Environment.IsDevelopment())
{
    app.UseExceptionHandler("/Error");
}

app.UseRouting();
app.UseAuthorization();

app.MapStaticAssets();
app.MapRazorPages()
    .WithStaticAssets();

app.MapPost("/api/scan", async (ScanRequest request, ScanService scanService, CancellationToken cancellationToken) =>
{
    var items = await scanService.ScanAsync(request.SourceIds, cancellationToken);
    return Results.Ok(new { items, total = items.Count });
});

app.MapPost("/api/uploads", async (HttpRequest request, RunStore runStore, CancellationToken cancellationToken) =>
{
    if (!request.HasFormContentType)
    {
        return Results.BadRequest(new { error = "multipart/form-data is required." });
    }

    var form = await request.ReadFormAsync(cancellationToken);
    var items = await runStore.SaveUploadsAsync(form.Files, cancellationToken);
    return Results.Ok(new { items, total = items.Count });
});

app.MapPost("/api/jobs", async (CreateJobCommand command, RunStore runStore, CancellationToken cancellationToken) =>
{
    try
    {
        var created = await runStore.CreateJobAsync(command, cancellationToken);
        return Results.Ok(new { jobId = created.JobId, runDirectory = created.RunDirectory });
    }
    catch (InvalidOperationException ex)
    {
        return Results.BadRequest(new { error = ex.Message });
    }
});

app.MapGet("/api/jobs/{id}", async (string id, RunStore runStore, CancellationToken cancellationToken) =>
{
    var status = await runStore.GetJobStatusAsync(id, cancellationToken);
    return status is null ? Results.NotFound() : Results.Ok(status);
});

app.MapGet("/runs/{id}/download", async (string id, RunStore runStore, CancellationToken cancellationToken) =>
{
    try
    {
        var archivePath = await runStore.BuildRunArchiveAsync(id, cancellationToken);
        return archivePath is null
            ? Results.NotFound()
            : Results.File(archivePath, "application/zip", $"{id}.zip");
    }
    catch (InvalidOperationException ex)
    {
        return Results.BadRequest(new { error = ex.Message });
    }
});

app.MapPost("/api/settings/huggingface", async (HuggingFaceSaveRequest request, SettingsStore settingsStore, HuggingFaceAccessService accessService, CancellationToken cancellationToken) =>
{
    await settingsStore.SaveHuggingFaceAsync(request.Token, request.TermsConfirmed, cancellationToken);
    var snapshot = await accessService.GetSnapshotAsync(cancellationToken);
    return Results.Ok(snapshot);
});

app.MapGet("/api/settings/huggingface/status", async (HuggingFaceAccessService accessService, CancellationToken cancellationToken) =>
{
    var snapshot = await accessService.GetSnapshotAsync(cancellationToken);
    return Results.Ok(snapshot);
});

app.MapGet("/set-language", (string lang, string? returnUrl, LanguageService languageService, HttpContext httpContext) =>
{
    languageService.ApplySelection(httpContext.Response, lang);
    var target = string.IsNullOrWhiteSpace(returnUrl) ? "/" : returnUrl;
    if (!Uri.IsWellFormedUriString(target, UriKind.Relative))
    {
        target = "/";
    }

    return Results.Redirect(target);
});

app.Run();
