using Messenger.Domain;
namespace Messenger.Storage;

public sealed class InMemoryMessengerStore(CursorCodec cursors) : IMessengerStore
{
    // One lock protects whole transactions, including reads and snapshots.
    // ConcurrentDictionary alone cannot make check-then-insert atomic.
    private readonly object gate = new();
    private readonly Dictionary<Guid, User> users = new();
    private readonly HashSet<string> usernames = new(StringComparer.Ordinal);
    private readonly Dictionary<Guid, Chat> chats = new();
    private readonly Dictionary<Guid, List<Message>> messages = new();
    private DateTime lastCreated;

    private DateTime NextTimestamp()
    {
        // Called under gate. Preserve insertion order even when wall time moves backwards.
        var now = DateTime.UtcNow;
        lastCreated = now > lastCreated ? now : lastCreated.AddTicks(1);
        return lastCreated;
    }

    public Task<User> CreateUserAsync(string username, string displayName)
    {
        lock (gate)
        {
            if (!usernames.Add(username)) throw new ApiException(409, "conflict", "Username is already used.");
            var user = new User(Guid.NewGuid(), username, displayName, NextTimestamp());
            users.Add(user.Id, user);
            return Task.FromResult(user);
        }
    }
    public Task<User?> FindUserAsync(Guid id)
    {
        lock (gate) return Task.FromResult(users.GetValueOrDefault(id));
    }
    public Task<Chat> CreateChatAsync(Guid actor, string title, IReadOnlyList<Guid> members)
    {
        lock (gate)
        {
            if (!members.Contains(actor) || members.Any(id => !users.ContainsKey(id))) throw ApiException.Invalid();
            var chat = new Chat(Guid.NewGuid(), title, Array.AsReadOnly(members.ToArray()), NextTimestamp());
            chats.Add(chat.Id, chat);
            messages.Add(chat.Id, new List<Message>());
            return Task.FromResult(chat);
        }
    }
    private Chat RequireChat(Guid actor, Guid id)
    {
        if (!chats.TryGetValue(id, out var chat) || !chat.MemberIds.Contains(actor)) throw ApiException.NotFound();
        return chat;
    }
    public Task<Chat> GetChatAsync(Guid actor, Guid chat)
    {
        lock (gate) return Task.FromResult(RequireChat(actor, chat));
    }
    public Task<Page<Chat>> ListChatsAsync(Guid actor, PageRequest page)
    {
        lock (gate) return Task.FromResult(cursors.Read(chats.Values.Where(c => c.MemberIds.Contains(actor)), $"chats:{actor:D}", page));
    }
    public Task<Message> AddMessageAsync(Guid actor, Guid chat, string text)
    {
        lock (gate)
        {
            RequireChat(actor, chat);
            var message = new Message(Guid.NewGuid(), chat, actor, text, NextTimestamp());
            messages[chat].Add(message);
            return Task.FromResult(message);
        }
    }
    public Task<Page<Message>> ListMessagesAsync(Guid actor, Guid chat, PageRequest page)
    {
        lock (gate)
        {
            RequireChat(actor, chat);
            return Task.FromResult(cursors.Read(messages[chat], $"messages:{chat:D}", page));
        }
    }
}
