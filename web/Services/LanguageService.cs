using System.Text.Json;

namespace Video2Timeline.Web.Services;

public sealed record SupportedLanguage(string Code, string NativeName);

internal sealed record LanguageDefinition(string Code, string NativeName, IReadOnlyList<string> Aliases);

internal sealed record LanguageCatalog(string DefaultLanguage, IReadOnlyList<LanguageDefinition> Definitions);

public sealed class LanguageService(IWebHostEnvironment environment, ILogger<LanguageService> logger)
{
    public const string CookieName = "video2timeline_lang";

    private readonly Lazy<LanguageCatalog> _catalog = new(() => LoadCatalog(environment, logger));

    public IReadOnlyList<SupportedLanguage> GetSupportedLanguages() =>
        _catalog.Value.Definitions.Select(static item => new SupportedLanguage(item.Code, item.NativeName)).ToArray();

    public string Resolve(HttpRequest request)
    {
        var fromQuery = Normalize(request.Query["lang"].ToString());
        if (fromQuery is not null)
        {
            return fromQuery;
        }

        if (request.Cookies.TryGetValue(CookieName, out var cookieValue))
        {
            var fromCookie = Normalize(cookieValue);
            if (fromCookie is not null)
            {
                return fromCookie;
            }
        }

        var header = request.Headers.AcceptLanguage.ToString();
        if (!string.IsNullOrWhiteSpace(header))
        {
            var first = header.Split(',', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries)
                .Select(static value => value.Split(';', StringSplitOptions.TrimEntries)[0])
                .Select(Normalize)
                .FirstOrDefault(static value => value is not null);
            if (first is not null)
            {
                return first;
            }
        }

        return _catalog.Value.DefaultLanguage;
    }

    public void ApplySelection(HttpResponse response, string language)
    {
        var normalized = Normalize(language) ?? _catalog.Value.DefaultLanguage;
        response.Cookies.Append(
            CookieName,
            normalized,
            new CookieOptions
            {
                IsEssential = true,
                Expires = DateTimeOffset.UtcNow.AddYears(1),
                SameSite = SameSiteMode.Lax,
            });
    }

    public string? Normalize(string? language)
    {
        if (string.IsNullOrWhiteSpace(language))
        {
            return null;
        }

        var lower = language.Trim().ToLowerInvariant();
        foreach (var definition in _catalog.Value.Definitions)
        {
            if (lower.Equals(definition.Code.ToLowerInvariant(), StringComparison.Ordinal))
            {
                return definition.Code;
            }

            foreach (var alias in definition.Aliases)
            {
                var normalizedAlias = alias.Trim().ToLowerInvariant();
                if (lower.Equals(normalizedAlias, StringComparison.Ordinal) ||
                    lower.StartsWith($"{normalizedAlias}-", StringComparison.Ordinal))
                {
                    return definition.Code;
                }
            }
        }

        return null;
    }

    private static LanguageCatalog LoadCatalog(IWebHostEnvironment environment, ILogger<LanguageService> logger)
    {
        var path = ResolveCatalogPath(environment);
        if (path is null)
        {
            logger.LogWarning("Language catalog was not found. Falling back to built-in defaults.");
            return GetDefaultCatalog();
        }

        try
        {
            var json = File.ReadAllText(path);
            var definition = JsonSerializer.Deserialize<LanguageCatalogDocument>(json);
            if (definition?.Languages is { Count: > 0 })
            {
                var languages = definition.Languages
                    .Where(static item => !string.IsNullOrWhiteSpace(item.Code) && !string.IsNullOrWhiteSpace(item.NativeName))
                    .Select(static item => new LanguageDefinition(
                        item.Code,
                        item.NativeName,
                        item.Aliases?.Where(static alias => !string.IsNullOrWhiteSpace(alias)).ToArray()
                            ?? [item.Code]))
                    .ToArray();

                if (languages.Length > 0)
                {
                    var defaultLanguage = languages.Any(item => string.Equals(item.Code, definition.DefaultLanguage, StringComparison.OrdinalIgnoreCase))
                        ? languages.First(item => string.Equals(item.Code, definition.DefaultLanguage, StringComparison.OrdinalIgnoreCase)).Code
                        : languages[0].Code;
                    return new LanguageCatalog(defaultLanguage, languages);
                }
            }
        }
        catch (Exception ex)
        {
            logger.LogWarning(ex, "Failed to load language catalog from {LanguageCatalogPath}", path);
        }

        return GetDefaultCatalog();
    }

    private static string? ResolveCatalogPath(IWebHostEnvironment environment)
    {
        var candidates = new[]
        {
            Path.Combine(AppContext.BaseDirectory, "Resources", "Locales", "languages.json"),
            Path.Combine(environment.ContentRootPath, "Resources", "Locales", "languages.json"),
        };

        return candidates.FirstOrDefault(File.Exists);
    }

    private static LanguageCatalog GetDefaultCatalog() =>
        new(
            "ja",
            [
                new("ja", "日本語", ["ja"]),
                new("en", "English", ["en"]),
                new("zh-CN", "简体中文", ["zh-cn", "zh-sg", "zh-hans"]),
                new("zh-TW", "繁體中文", ["zh-tw", "zh-hk", "zh-mo", "zh-hant"]),
                new("ko", "한국어", ["ko"]),
                new("es", "Español", ["es"]),
                new("fr", "Français", ["fr"]),
                new("de", "Deutsch", ["de"]),
                new("pt", "Português", ["pt"]),
            ]);
}

internal sealed class LanguageCatalogDocument
{
    public string DefaultLanguage { get; set; } = "ja";

    public List<LanguageCatalogLanguageDocument> Languages { get; set; } = [];
}

internal sealed class LanguageCatalogLanguageDocument
{
    public string Code { get; set; } = string.Empty;

    public string NativeName { get; set; } = string.Empty;

    public List<string>? Aliases { get; set; }
}
