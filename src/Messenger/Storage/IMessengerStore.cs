using Messenger.Domain;
namespace Messenger.Storage;

// Each method is one atomic operation. A future SQL implementation must preserve
// these boundaries (including membership checks), not merely replace dictionaries.
public interface IMessengerStore
{
    Task<User> CreateUserAsync(string username, string displayName);
    Task<User?> FindUserAsync(Guid id);
    Task<Chat> CreateChatAsync(Guid actor, string title, IReadOnlyList<Guid> members);
    Task<Chat> GetChatAsync(Guid actor, Guid chat);
    Task<Page<Chat>> ListChatsAsync(Guid actor, PageRequest page);
    Task<Message> AddMessageAsync(Guid actor, Guid chat, string text);
    Task<Page<Message>> ListMessagesAsync(Guid actor, Guid chat, PageRequest page);
}
