using System.Security.Cryptography;
using System.Text;
using Messenger.Domain;
namespace Messenger.Storage;

public sealed class CursorCodec
{
    // Cursors live only as long as this in-memory process. Lab2/3 will need a shared key.
    private readonly byte[] key = RandomNumberGenerator.GetBytes(32);

    public string Encode(string scope, IOrderedEntity item)
    {
        var data = Encoding.UTF8.GetBytes($"{scope}|{item.CreatedAt.Ticks}|{item.Id:D}");
        return Convert.ToBase64String(data) + "." + Convert.ToBase64String(HMACSHA256.HashData(key, data));
    }

    public (long Ticks, Guid Id) Decode(string cursor, string scope)
    {
        try
        {
            if (cursor.Length > 1024) throw ApiException.Invalid();
            var parts = cursor.Split('.');
            if (parts.Length != 2) throw ApiException.Invalid();
            var data = Convert.FromBase64String(parts[0]);
            var signature = Convert.FromBase64String(parts[1]);
            if (!CryptographicOperations.FixedTimeEquals(signature, HMACSHA256.HashData(key, data)))
                throw ApiException.Invalid();
            var fields = Encoding.UTF8.GetString(data).Split('|');
            if (fields.Length != 3 || fields[0] != scope || !long.TryParse(fields[1], out var ticks)
                || !Guid.TryParseExact(fields[2], "D", out var id)) throw ApiException.Invalid();
            return (ticks, id);
        }
        catch (FormatException) { throw ApiException.Invalid(); }
    }

    public Page<T> Read<T>(IEnumerable<T> source, string scope, PageRequest request) where T : IOrderedEntity
    {
        var ordered = source.OrderBy(x => x.CreatedAt).ThenBy(x => x.Id).AsEnumerable();
        if (request.Cursor is not null)
        {
            var after = Decode(request.Cursor, scope);
            ordered = ordered.Where(x => x.CreatedAt.Ticks > after.Ticks ||
                (x.CreatedAt.Ticks == after.Ticks && x.Id.CompareTo(after.Id) > 0));
        }
        var batch = ordered.Take(request.Limit + 1).ToArray();
        var items = batch.Take(request.Limit).ToArray();
        return new Page<T>(items, batch.Length > request.Limit ? Encode(scope, items[^1]) : null);
    }
}
