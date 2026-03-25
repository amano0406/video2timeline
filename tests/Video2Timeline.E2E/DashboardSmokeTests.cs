using System.Text.RegularExpressions;
using Microsoft.Playwright;

namespace Video2Timeline.E2E;

[TestClass]
public sealed class DashboardSmokeTests : PageTest
{
    private static TestAppFixture _fixture = null!;

    [ClassInitialize]
    public static async Task InitializeAsync(TestContext _)
    {
        _fixture = await TestAppFixture.StartAsync();
    }

    [ClassCleanup]
    public static async Task CleanupAsync()
    {
        if (_fixture is not null)
        {
            await _fixture.DisposeAsync();
        }
    }

    [TestMethod]
    public async Task Root_Redirects_To_NewJob()
    {
        await SetLanguageAsync("en", "/");

        await Expect(Page).ToHaveURLAsync(new Regex(".*/jobs/new$"));
        await Expect(Page.Locator("html")).ToHaveAttributeAsync("lang", "en");
        await Expect(Page.GetByRole(AriaRole.Heading, new() { Name = "New Job" })).ToBeVisibleAsync();
        await Expect(Page.GetByRole(AriaRole.Link, new() { Name = "Jobs" })).ToBeVisibleAsync();
    }

    [TestMethod]
    public async Task Settings_Shows_Save_Button_And_Theme_Options()
    {
        await SetLanguageAsync("en", "/settings");

        await Expect(Page.Locator("html")).ToHaveAttributeAsync("lang", "en");
        await Expect(Page.GetByRole(AriaRole.Heading, new() { Name = "Settings" })).ToBeVisibleAsync();
        await Expect(Page.GetByRole(AriaRole.Button, new() { Name = "Save Settings" })).ToBeVisibleAsync();
        await Expect(Page.GetByText("Workbench")).ToBeVisibleAsync();
        await Expect(Page.GetByText("Classic")).ToBeVisibleAsync();
    }

    [TestMethod]
    public async Task Jobs_Page_Shows_Completed_Run()
    {
        await SetLanguageAsync("en", "/jobs");

        await Expect(Page.GetByRole(AriaRole.Heading, new() { Name = "Jobs", Exact = true })).ToBeVisibleAsync();
        await Expect(Page.GetByText("There is no active job right now.")).ToBeVisibleAsync();
        await Expect(Page.GetByText(_fixture.CompletedJobId)).ToBeVisibleAsync();
        await Expect(Page.GetByRole(AriaRole.Link, new() { Name = "ZIP" })).ToBeVisibleAsync();
    }

    [TestMethod]
    public async Task CompletedRunDetails_ExposeZip_AndTimeline()
    {
        await SetLanguageAsync("en", $"/runs/{_fixture.CompletedJobId}");

        await Expect(Page.GetByRole(AriaRole.Heading, new() { Name = _fixture.CompletedJobId })).ToBeVisibleAsync();
        await Expect(Page.GetByRole(AriaRole.Link, new() { Name = "Download ZIP" })).ToBeVisibleAsync();
        await Expect(Page.GetByRole(AriaRole.Link, new() { Name = _fixture.CompletedMediaId })).ToBeVisibleAsync();

        await Page.GetByRole(AriaRole.Link, new() { Name = _fixture.CompletedMediaId }).ClickAsync();
        await Expect(Page).ToHaveURLAsync(new Regex($".*/runs/{_fixture.CompletedJobId}/{_fixture.CompletedMediaId}$"));
        await Expect(Page.Locator("pre")).ToContainTextAsync("Video Timeline");
        await Expect(Page.Locator("pre")).ToContainTextAsync("public test sample");
    }

    [TestMethod]
    public async Task CompletedRunDetails_CanDownloadZip()
    {
        await SetLanguageAsync("en", $"/runs/{_fixture.CompletedJobId}");

        var download = await Page.RunAndWaitForDownloadAsync(async () =>
        {
            await Page.GetByRole(AriaRole.Link, new() { Name = "Download ZIP" }).ClickAsync();
        });

        Assert.AreEqual($"{_fixture.CompletedJobId}.zip", download.SuggestedFilename);
    }

    private async Task SetLanguageAsync(string language, string returnPath)
    {
        var encoded = Uri.EscapeDataString(returnPath);
        await Page.GotoAsync($"{_fixture.BaseUrl}/set-language?lang={language}&returnUrl={encoded}");
    }
}
