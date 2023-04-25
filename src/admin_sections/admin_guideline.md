[TOC]

&nbsp;

# Admin panel guidelines

&nbsp;

##Accounts

&nbsp;

###Default Avatars
Purpose: Managing default avatars for new users.
Administrator has possibility to add/delete avatars for newly registered users via upload field. 

&nbsp;

###Users
Users are platform users. In the user window, viewing and editing user info is available.

Last login is a date and time for the user's last login. It is updated automatically.
**" Username"** is the user's metamask address.

**"Active"** checkbox is used to designate the user as active, disable it to prevent user from logging in.
Date joined is created automatically when a User is created.

Avatar ipfs is stored as an IPFS hash of the image file uploaded by the user. It can be changed via file upload widget.

The following fields are for an additional info the user can provide and are can be modified by admin:

1) **Display name** is a custom name that the User can set. It will be displayed instead of the user’s address.

2) **Bio** field is for the users to write about themselves. It will be displayed in their profiles.

3) **Twitter**, **Instagram** and other media are for user’s links to their social media profiles or their personal site.

&nbsp;

##Games

&nbsp;

Section for managing games.

&nbsp;

###**GameCompanies**
The list of all games. For each game, it is possible to approve or decline it (if not done previously), change avatar, banner and some media links.
Also it is possible to change the names and avatars of categories and subcategories and delete them.
Filtering by approve status is available.

&nbsp;

###**Default game avatars** and **Default game banners**
Subsections for setting default pictures for the games which users can override later then customising their games. Works similar to the **ACCOUNTS** **Default avatars** section

&nbsp;

###**Categories** and **Subcategories**
Lists of awaiting requests of adding categories/subcategories to the game. Only unprocessed requests are shown here to ease managing.

&nbsp;

###**Game Collections**
The list of awaiting requests to add collections to the game. Only unprocessed requests are shown, other collections can be found and managed in the **STORE Collections** section

&nbsp;

##Activity

&nbsp;

There are three subsections in the activity section: 'Bids historys', 'Token historys' and 'User actions'.

They mostly have just utility function and are in read-only state.

&nbsp;

###Bids historys

Represents user **bids** history (Bidding on auction).

&nbsp;

###Token historys

Represents user actions with **tokens** (listings, buying, transfering…)

&nbsp;

###User actions
Represents user ((“social”** actions (likes, followings)

&nbsp;

##Networks

&nbsp;

Interface which represents network control in the project.

Mainly it should be used for:

1) checking contract addresses (it is strongly not recommended to change them without developer’s notice)

2) managing list of RPC-endpoints (**“Providers”** inline). This is a list of available RPC-endpoints for backend communication with given blockchain. Could be rearranged freely by changing or adding new rpc.


&nbsp;

##Promotion

&nbsp;

Section for managing promotions

&nbsp;

### Promotion Settings

&nbsp;

Subsection for setting promotion packages for each network.

**Slots** represent amount of simultaneously active promotions.

&nbsp;

In **PROMOTION DATA** inline lays the information about packages:

**number** of promoting days;

**price** in US dolars;

&nbsp;
   
New package can be added by "Add another promotion options" in the bottom.

Deleting package can be performed by choosing **DELETE?** checkbox against package data and saving 

&nbsp;

### Promotions

&nbsp;

Read-only subsection with information about promotions with filtering by **status**

&nbsp;

##Rates

&nbsp;

This section stores exchange rates based on coingecko rates. They are updated automatically every 5 minutes. 

The fields are the Rate itself, Coin node name (coingecko slug name), Symbol name, Image (token logo), Address and decimal placement for the rate.
Rates info is set in read-only state to prevent manipulations with currency rate and/or breaking rates update routine.

&nbsp;

##Store

&nbsp;

###Bids
Bids for tokens are displayed here.

Fields displayed are: Token that the bid is made on, Quantity, User that has made the bid, bid amount, currency.
All info is in read-only state.

&nbsp;

###Categories
Used for creating/deleting categories (for explore page).

**Category** is created by clicking add category, entering name and uploading image.

For already created categories it is possible to change image or name.

&nbsp;

###Collections

Collections are displayed here.
In view mode, the collection name, address, standard, author of the collection, network, all social media and delete status are displayed.

In edit mode **deleted** is a “ban” function if for any reasons collection should be deleted from marketplace and **category** is for linking collection with category. 

Also it is possible to edit collection's social media and description.

&nbsp;

###Ownership

**‘Ownerships’** describes what tokens are owned by which user. 

Manual changes could break communication with blockchain, so this section is read-only.

&nbsp;

###Tokens
In this subsection are mentioned all tokens supported by platform. To prevent desync with blockchain, this section is mostly read_only. 

The only editable field are **"Deleted"** (blocking token from marketplace).

Search by name and filtering through token standards, status and collection name are available.

&nbsp;

##Support
Section for managing platform configuration

&nbsp;

###Configs
Subsection for setting global parameters for platform.

Currently consists of 4 options:

**Top users period** - sets limits in days for filtering user activity while updating top users chart (i.e. if 7 is specified, only data of the last week will be used for charts).

**Top users period** - sets limits in days for filtering user activity while updating top collections chart (i.e. if 7 is specified, only data of the last week will be used for charts).

For both fields, leaving it blank corresponds to **"count for all time"**.

**Approval timeout** - allows to check approval revokes from nft collections more or less frequently, lowering amount of web3 requests by some amount. 

**Max royalty percentage** - sets the limit to royalty percentage when modifying the collection info.

&nbsp;

###EmailConfig
This subsection is created for managing sender and receiver of email notifications.
Subsection for managing admin email receiver address and admin sending info (address, password(encrypted), smtp server domain, etc)
Only one pair of sender and receiver could exist at once, incorrect changes which could intefere with email logic are blocked by validation system.

###Email Templates
Subsection for customisation of game email bodies. Dynamic info such as user's name or game name cane be used in the placeholder {}.
List of available placeholders is mentioned in the "hints" field.
