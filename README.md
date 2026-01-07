This project is a fork of <https://github.com/modelcontextprotocol/python-sdk> that adds
support for the gRPC transport described in
[SEP-1352](https://github.com/modelcontextprotocol/modelcontextprotocol/issues/1352).
This is a proof-of-concept (POC) in support of that SEP.

This fork may or may not be maintained in the long term.  Ideally, if the SEP is
accepted, we will upstream these changes and abandon this fork.  Alternatively,
if we can introduce a pluggable transport API to the upstream SDK, then we can
distribute the gRPC transport as a separate package without having to fork the entire
SDK, in which case would also abandon this fork.  However, if we can't make either
of those options work, then we will continue to maintain this fork, periodically
syncing changes from the upstream SDK.

See also the README from the upstream SDK at <https://github.com/modelcontextprotocol/python-sdk/blob/main/README.md>.

### gRPC Transport

## Features

✅ Supported ❌ Not Supported ⚪ Not Needed/Not Applicable

| Feature | gRPC Transport | Comment |
| :--- | :---: | :--- |
| Initialisation | ✅ | Was done as version negotion |
| Server-Tool | ✅ | |
| Server-Client | ✅ | |
| Server-Prompt | ❌ | |
| Client-Roots | ❌ | |
| Client-Sampling | ❌ | |
| Client-Elicitation | ❌ | |
| Utility-Ping | ⚪ | This is not needed for gRPC transport |
| Utility-Cancellation | ✅ | Cancellation of RPC call in gRPC transport |
| Utility-Progress | ✅ | |
| Utility-Completion | ❌ | |
| Utility-Logging | ❌ | |
| Utility-Pagination | ❌ | |
