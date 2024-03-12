# MimiKeePass

Main features:

* password-based SSH authentication with OpenSSH with the password stored in KeepPass (`.kdbx`) files.

Other features:

* can serve password from multiple KeePass files;
* automatically reloads the `.kdbx` file on change;
* support for socket-activation;
* support for exiting after some idle duration;
* support for KeePass [field references](https://keepass.info/help/base/fieldrefs.html);
* some support for bastions.


## Basic usage

### Running the KeePass daemon

Running the MimiKeePass daemon:

~~~sh
mimikeepass serve ./secrets.kdbx
~~~

This will prompt for the KeePass file(s) password(s) and will provide passwords to client applications.

### CLI interface

~~~sh
mimikeepass password --url http://www.example.com --username john
~~~

### OpenSSH client

In your KeePass file, add an entry for your SSH server:

* URL of the form `ssh://server1.example.com`;
* login `johndoe`;
* password.

The OpenSSH integration supports password-based authentication.
You might need to disable keyboard interactive authentication
for this server in you OpenSSH client configuration (`~/.ssh/ssh_config`):

~~~
Host server1.example.com
User johndoe
PreferredAuthentications publickey,password
~~~

Run OpenSSH with MimiKeePass integration:

~~~sh
miikeepass-run ssh server1.example.com
~~~

### OpenSSH client with SSH bastion

If you have a bestion server which accepts connections of the form:

~~~
Host bastion.example.com
User johndoe@idp.example.com
PreferredAuthentications publickey,password

Host server1.example.com
Hostname bastion.example.com
User root@XXXX@server1:SSH:XXXX:johndoe@idp.example.com
PreferredAuthentications publickey,password

Host server1.example.com
Hostname bastion.example.com
User root@XXXX@server2:SSH:XXXX:johndoe@idp.example.com
PreferredAuthentications publickey,password
~~~

You can use a shared KeePass entry:

* URL of the form `ssh://bastion.example.com`;
* login `johndoe@idp.example.com`;
* password.


## Stability

CLI interface is probably going to be quite stable.

Python API is not stable (for now).

Protocol (varlink) interface is not stable (for now).


## Potential impovements

* logging
* support for OpenVPN (using the management interface)
* notifications using OSC 777, OSC 99, OSC 9
* notifications using BEL
* FreeDesktop [notifications](https://specifications.freedesktop.org/notification-spec/notification-spec-latest.html)
* optional integration with FreeDesktop [Secret Service](https://specifications.freedesktop.org/secret-service/latest/)?


## Questions

### OpenSSH integration

**Why using password based authentication when you can use public key authentication?**

If you can use public key authentication authentication, you probably should.
However sometimes, you need to connect to SSH servers which do not support
public key authentication for some reason.

### Misc.

**Why not using Secret Service (possibly with KeePassXC support for the Secret Service interface)?**

You can only have a single Secret Service daemon running in your session at the same time.
However, you might want to have some secrets stored in your system Secret Service and other password
stored in a KeePass file. Using a dedicated daemon  which is not using the Secret Service API
makes it possible to run a Mimikeepass independently of your system Secret Service daemon.

You can even launch several independant MimiKeePass daemons (using different sockets).
This is achieved using the `MIMIKEEPASS_SOCKET` environment variable.
