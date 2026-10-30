using Messenger.Domain;
using Messenger.Storage;
namespace Messenger.Api;

// Replace this adapter with Bearer session authentication in lab2.
public interface ICurrentUser
{
    Task<User> RequireAsync(HttpContext context);
}
public sealed class HeaderCurrentUser(IMessengerStore store) : ICurrentUser
{
    public async Task<User> RequireAsync(HttpContext context)
    {
        var header = context.Request.Headers["X-User-Id"];
        if (header.Count != 1 || !Guid.TryParseExact(header[0], "D", out var id)) throw ApiException.Unauthorized();
        return await store.FindUserAsync(id) ?? throw ApiException.Unauthorized();
    }
}
