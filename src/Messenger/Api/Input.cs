using System.Globalization;
using System.Text;
using System.Text.Json;
using System.Text.RegularExpressions;
using Messenger.Domain;
namespace Messenger.Api;

public static class Input
{
    public static async Task<JsonDocument> Body(HttpRequest request, params string[] fields)
    {
        if (!request.HasJsonContentType()) throw new ApiException(415, "unsupported_media_type", "JSON required.");
        var doc = await JsonDocument.ParseAsync(request.Body, cancellationToken: request.HttpContext.RequestAborted);
        try
        {
            if (doc.RootElement.ValueKind != JsonValueKind.Object) throw ApiException.Invalid();
            var seen = new HashSet<string>(StringComparer.Ordinal);
            foreach (var property in doc.RootElement.EnumerateObject())
                if (!fields.Contains(property.Name) || !seen.Add(property.Name)) throw ApiException.Invalid();
            if (seen.Count != fields.Length) throw ApiException.Invalid();
            return doc;
        }
        catch (InvalidOperationException) { doc.Dispose(); throw ApiException.Invalid(); }
        catch { doc.Dispose(); throw; }
    }
    public static string Text(JsonElement body, string name, int max)
    {
        var value = body.GetProperty(name);
        if (value.ValueKind != JsonValueKind.String) throw ApiException.Invalid();
        var text = String(value);
        if (string.IsNullOrWhiteSpace(text)) throw ApiException.Invalid();
        // string.Length counts UTF-16 units; an emoji usually occupies two units.
        var count = 0;
        var remaining = text.AsSpan();
        while (!remaining.IsEmpty)
        {
            if (Rune.DecodeFromUtf16(remaining, out _, out var consumed) != System.Buffers.OperationStatus.Done)
                throw ApiException.Invalid();
            count++;
            remaining = remaining[consumed..];
        }
        if (count > max) throw ApiException.Invalid();
        return text;
    }
    private static string String(JsonElement value)
    {
        // System.Text.Json can defer UTF-8/surrogate validation until GetString.
        try { return value.GetString()!; }
        catch (InvalidOperationException) { throw ApiException.Invalid(); }
    }
    public static string Username(JsonElement body)
    {
        var name = Text(body, "username", 32);
        if (!Regex.IsMatch(name, @"\A[a-z0-9_]{3,32}\z", RegexOptions.CultureInvariant)) throw ApiException.Invalid();
        return name;
    }
    public static Guid Id(string? raw)
    {
        if (!Guid.TryParseExact(raw, "D", out var id)) throw ApiException.Invalid();
        return id;
    }
    public static IReadOnlyList<Guid> Members(JsonElement body)
    {
        var value = body.GetProperty("member_ids");
        if (value.ValueKind != JsonValueKind.Array || value.GetArrayLength() is < 1 or > 100) throw ApiException.Invalid();
        var ids = new List<Guid>();
        foreach (var item in value.EnumerateArray())
        {
            if (item.ValueKind != JsonValueKind.String) throw ApiException.Invalid();
            ids.Add(Id(String(item)));
        }
        if (ids.Distinct().Count() != ids.Count) throw ApiException.Invalid();
        return ids;
    }
    public static PageRequest Page(HttpRequest request)
    {
        var limit = 50;
        if (request.Query.TryGetValue("limit", out var value))
            if (value.Count != 1 || !int.TryParse(value[0], NumberStyles.None, CultureInfo.InvariantCulture, out limit)
                || limit is < 1 or > 100) throw ApiException.Invalid();
        string? cursor = null;
        if (request.Query.TryGetValue("cursor", out var c))
        {
            if (c.Count != 1 || string.IsNullOrEmpty(c[0])) throw ApiException.Invalid();
            cursor = c[0];
        }
        return new PageRequest(limit, cursor);
    }
}
