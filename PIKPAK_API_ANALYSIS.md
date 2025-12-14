# PikPak API 接口分析报告

本文档基于 `pikpakcli` 源代码（`internal/pikpak/` 目录）分析 PikPak 官方后端 API 接口。

## 目录

1. [认证 (Authentication)](#1-认证-authentication)
2. [文件与文件夹管理 (File & Folder Management)](#2-文件与文件夹管理-file--folder-management)
3. [上传与下载 (Upload & Download)](#3-上传与下载-upload--download)
4. [用户信息 (User Info)](#4-用户信息-user-info)

---

## 1. 认证 (Authentication)

### 1.1 登录 (Login)

*   **代码位置**: `internal/pikpak/pikpak.go` (`Login` 方法)
*   **URL**: `https://user.mypikpak.com/v1/auth/signin`
*   **Method**: `POST`
*   **Content-Type**: `application/json; charset=utf-8`
*   **请求参数 (Body)**:
    ```json
    {
      "client_id": "YNxT9w7GMdWvEOKa",
      "client_secret": "dbw2OtmVEeuUvIptb1Coyg",
      "grant_type": "password",
      "username": "<ACCOUNT>",
      "password": "<PASSWORD>",
      "captcha_token": "<CAPTCHA_TOKEN>"
    }
    ```
*   **返回结构**:
    *   `access_token` (String): JWT Token
    *   `refresh_token` (String): 刷新 Token
    *   `sub` (String): 用户 ID
    *   `expires_in` (Int): 过期时间
    *   `error_code` (Int): 错误码 (0 为成功)
    *   `error` (String): 错误信息

### 1.2 获取验证码 Token (Get Captcha Token)

*   **代码位置**: `internal/pikpak/pikpak.go` (`getCaptchaToken` 方法)
*   **URL**: `https://user.mypikpak.com/v1/shield/captcha/init`
*   **Method**: `POST`
*   **Content-Type**: `application/json`
*   **请求参数 (Body)**:
    ```json
    {
      "client_id": "YNxT9w7GMdWvEOKa",
      "device_id": "<DEVICE_ID>",
      "action": "POST:https://user.mypikpak.com/v1/auth/signin",
      "meta": {
        "username": "<ACCOUNT>"
      }
    }
    ```
*   **返回结构**:
    *   `captcha_token` (String)

### 1.3 刷新 Token (Refresh Token)

*   **代码位置**: `internal/pikpak/refresh_token.go` (`RefreshToken` 方法)
*   **URL**: `https://user.mypikpak.com/v1/auth/token`
*   **Method**: `POST`
*   **请求参数 (Body)**:
    ```json
    {
      "client_id": "YNxT9w7GMdWvEOKa",
      "client_secret": "dbw2OtmVEeuUvIptb1Coyg",
      "grant_type": "refresh_token",
      "refresh_token": "<REFRESH_TOKEN>"
    }
    ```
*   **返回结构**:
    *   `access_token` (String)
    *   `refresh_token` (String)
    *   `expires_in` (Int)

### 1.4 验证验证码 Token (Auth Captcha Token)

*   **代码位置**: `internal/pikpak/captcha_token.go` (`AuthCaptchaToken` 方法)
*   **URL**: `https://user.mypikpak.com/v1/shield/captcha/init?client_id=YNxT9w7GMdWvEOKa`
*   **Method**: `POST`
*   **Content-Type**: `application/json; charset=utf-8`
*   **请求参数 (Body)**:
    ```json
    {
      "action": "<ACTION_STRING>", // e.g., "POST:/drive/v1/files"
      "captcha_token": "<CURRENT_CAPTCHA_TOKEN>",
      "client_id": "YNxT9w7GMdWvEOKa",
      "device_id": "<DEVICE_ID>",
      "meta": {
        "captcha_sign": "1.<SIGNATURE>",
        "user_id": "<USER_ID>",
        "package_name": "com.pikcloud.pikpak",
        "client_version": "1.21.0",
        "timestamp": "<TIMESTAMP>"
      },
      "redirect_uri": "https://api.mypikpak.com/v1/auth/callback"
    }
    ```
    *注*: `captcha_sign` 是通过 MD5 算法加盐计算得出的。

---

## 2. 文件与文件夹管理 (File & Folder Management)

### 2.1 获取文件列表 (Get Folder File List)

*   **代码位置**: `internal/pikpak/file.go` (`GetFolderFileStatList` 方法), `internal/pikpak/folder.go` (`GetFolderId` 方法)
*   **URL**: `https://api-drive.mypikpak.com/drive/v1/files`
*   **Method**: `GET`
*   **请求参数 (Query)**:
    *   `parent_id`: 父目录 ID (可选)
    *   `thumbnail_size`: `SIZE_MEDIUM` / `SIZE_LARGE`
    *   `limit`: 数量限制 (e.g., `500`)
    *   `with_audit`: `false`
    *   `filters`: JSON 字符串，例如 `{"trashed":{"eq":false}}`
    *   `page_token`: 分页 Token
*   **返回结构**:
    *   `next_page_token` (String)
    *   `files` (Array of `FileStat`):
        *   `kind`, `id`, `parent_id`, `name`, `user_id`, `size`, `file_extension`, `mime_type`
        *   `created_time`, `modified_time`, `icon_link`, `thumbnail_link`
        *   `md5_checksum`, `hash`, `phase`

### 2.2 获取单个文件详情 (Get File Detail)

*   **代码位置**: `internal/pikpak/file.go` (`GetFile` 方法)
*   **URL**: `https://api-drive.mypikpak.com/drive/v1/files/{fileId}`
*   **Method**: `GET`
*   **请求参数 (Query)**:
    *   `thumbnail_size`: `SIZE_MEDIUM`
*   **返回结构** (`File` 结构体):
    *   包含 `FileStat` 所有字段
    *   `revision`, `starred`, `web_content_link`
    *   `links`: 下载链接信息 (`application/octet-stream`)
    *   `medias`: 媒体信息
    *   `trashed`, `delete_time`, `original_url`

### 2.3 创建文件夹 (Create Folder)

*   **代码位置**: `internal/pikpak/folder.go` (`CreateFolder` 方法)
*   **URL**: `https://api-drive.mypikpak.com/drive/v1/files`
*   **Method**: `POST`
*   **Headers**:
    *   `X-Captcha-Token`, `X-Client-Version-Code`, `X-Peer-Id`, `X-User-Region`, `X-Alt-Capability`, `Country`
*   **请求参数 (Body)**:
    ```json
    {
      "kind": "drive#folder",
      "parent_id": "<PARENT_ID>",
      "name": "<FOLDER_NAME>"
    }
    ```
*   **返回结构**:
    *   `file.id` (String): 新创建文件夹的 ID

---

## 3. 上传与下载 (Upload & Download)

### 3.1 创建 URL 任务 (离线下载) (Create Url File)

*   **代码位置**: `internal/pikpak/url.go` (`CreateUrlFile` 方法)
*   **URL**: `https://api-drive.mypikpak.com/drive/v1/files`
*   **Method**: `POST`
*   **请求参数 (Body)**:
    ```json
    {
      "kind": "drive#file",
      "upload_type": "UPLOAD_TYPE_URL",
      "url": {
        "url": "<TARGET_URL>"
      },
      "parent_id": "<PARENT_ID>" // 可选
    }
    ```
*   **返回结构**:
    *   `task`: 包含任务状态 (e.g., `phase`)

### 3.2 极速秒传/初始化上传 (Upload File Init / SHA Upload)

*   **代码位置**: `internal/pikpak/upload.go` (`UploadFile`), `internal/pikpak/sha.go` (`CreateShaFile`)
*   **URL**: `https://api-drive.mypikpak.com/drive/v1/files`
*   **Method**: `POST`
*   **请求参数 (Body)**:
    ```json
    {
      "kind": "drive#file",
      "name": "<FILE_NAME>",
      "size": "<FILE_SIZE>",
      "hash": "<FILE_HASH>",
      "upload_type": "UPLOAD_TYPE_RESUMABLE",
      "objProvider": {
        "provider": "UPLOAD_TYPE_UNKNOWN"
      },
      "parent_id": "<PARENT_ID>" // 可选
    }
    ```
*   **返回结构**:
    *   如果 `phase` 为 `PHASE_TYPE_COMPLETE`，则秒传成功。
    *   如果 `phase` 为 `PHASE_TYPE_PENDING`，则需要继续上传 (见下文 Aliyun OSS 上传流程)。
    *   返回中包含 `resumable.params`，含有 OSS 上传所需的参数 (`access_key_id`, `access_key_secret`, `bucket`, `endpoint`, `key`, `security_token`)。

### 3.3 Aliyun OSS 上传流程 (当无法秒传时)

这部分直接与阿里云 OSS 交互，而不是 PikPak 业务服务器。

1.  **初始化 Multipart Upload**:
    *   **URL**: `https://{endpoint}/{key}?uploads`
    *   **Method**: `POST`
    *   **Headers**: `Authorization` (OSS 签名), `X-Oss-Security-Token`
    *   **返回**: `UploadId`

2.  **上传分片 (Upload Chunk)**:
    *   **URL**: `https://{endpoint}/{key}?uploadId={uploadId}&partNumber={partNumber}`
    *   **Method**: `PUT`
    *   **Body**: 文件分片数据
    *   **返回**: `ETag` (Header 中)

3.  **完成上传 (Complete Multipart Upload)**:
    *   **URL**: `https://{endpoint}/{key}?uploadId={uploadId}`
    *   **Method**: `POST`
    *   **Body** (XML): 包含所有分片的 PartNumber 和 ETag。

### 3.4 下载文件 (Download File)

*   **代码位置**: `internal/pikpak/download.go` (`Download` 方法)
*   **URL**: 动态 URL，来源于 `GetFile` 接口返回的 `links.application/octet-stream.url`
*   **Method**: `GET`
*   **Headers**:
    *   `User-Agent`: `ANDROID-com.pikcloud.pikpak/1.21.0`
    *   `Range`: `bytes={start}-` (支持断点续传)

---

## 4. 用户信息 (User Info)

### 4.1 获取配额 (Get Quota)

*   **代码位置**: `internal/pikpak/quota.go` (`GetQuota` 方法)
*   **URL**: `https://api-drive.mypikpak.com/drive/v1/about`
*   **Method**: `GET`
*   **返回结构** (`Quota`):
    *   `kind`
    *   `limit`: 总空间
    *   `usage`: 已用空间
    *   `usage_in_trash`: 回收站占用

---

## 5. 分享 (Share) - *New*

### 5.1 获取分享信息 (Get Share Info)

*   **URL**: `https://api-drive.mypikpak.com/drive/v1/share`
*   **Method**: `GET`
*   **Headers**:
    *   `X-Device-Id`: 必填
    *   `X-Captcha-Token`: 必填 (可能需要)
*   **请求参数 (Query)**:
    *   `share_id`: 分享 ID (例如 `VOKb91vMpLUddAoRhJXcCYHQo1`)
    *   `pass_code`: 提取码/Pass Code (例如 `AAAABF_tZ4hH7dxk683DdWOfo1_VOK`)
    *   `client_id`: 客户端 ID (例如 `YNxT9w7GMdWvEOKa`)
*   **返回结构**:
    *   包含分享的基本信息，如 `share_status`, `title`, `pass_code_token` 等。
    *   `files`: 包含根目录/文件的基本信息 (例如 `parent_id` 即为根目录 ID)。
    *   `pass_code_token`: 用于后续访问分享内容的鉴权令牌。

### 5.2 获取分享文件夹内容 (Get Share Folder Detail)

*   **URL**: `https://api-drive.mypikpak.com/drive/v1/share/detail`
*   **Method**: `GET`
*   **Headers**:
    *   `X-Device-Id`: 必填
    *   `X-Captcha-Token`: 必填 (Action: `GET:/drive/v1/share/detail`)
*   **请求参数 (Query)**:
    *   `share_id`: 分享 ID
    *   `pass_code_token`: 从 `Get Share Info` 接口获取的令牌
    *   `parent_id`: 父目录 ID (如果是根目录，则使用 `Get Share Info` 返回的目录 ID)
    *   `limit`: 数量限制
    *   `thumbnail_size`: `SIZE_LARGE` / `SIZE_MEDIUM`
    *   `order`: 排序方式 (例如 `6`)
    *   `client_id`: 客户端 ID
*   **返回结构**:
    *   `files`: 文件列表，包含 `id`, `name`, `size`, `hash` 等详细信息。
