package main

import (
	"crypto/rand"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/url"

	"github.com/52funny/pikpakcli/internal/pikpak"
	"github.com/sirupsen/logrus"
)

// Generate a random device ID
func generatedeviceID() string {
	b := make([]byte, 8) // 16 chars hex
	rand.Read(b)
	return hex.EncodeToString(b)
}

type ShareResponse struct {
	Files []struct {
		ID   string `json:"id"`
		Name string `json:"name"`
		Kind string `json:"kind"`
	} `json:"files"`
	PassCodeToken string `json:"pass_code_token"`
}

func main() {
	logrus.SetLevel(logrus.DebugLevel)

	deviceID := generatedeviceID()
	fmt.Printf("Using Device ID: %s\n", deviceID)

	p := pikpak.NewPikPak("dummy", "dummy")
	p.DeviceId = deviceID

	// 1. Get Captcha Token for Share Info
	fmt.Println("1. Getting Captcha Token for Share Info...")
	action := "GET:/drive/v1/share"
	err := p.AuthCaptchaToken(action)
	if err != nil {
		fmt.Printf("Error getting captcha token: %v\n", err)
		return
	}
	captchaTokenShare := p.CaptchaToken
	fmt.Println("Captcha Token obtained.")

	// 2. Call Share API to get Root Folder and PassCodeToken
	shareID := "VOKb91vMpLUddAoRhJXcCYHQo1"
	passCode := "AAAABF_tZ4hH7dxk683DdWOfo1_VOK"
	clientID := "YNxT9w7GMdWvEOKa"

	targetURL := "https://api-drive.mypikpak.com/drive/v1/share"
	params := url.Values{}
	params.Add("share_id", shareID)
	params.Add("pass_code", passCode)
	params.Add("client_id", clientID)

	fullURL := fmt.Sprintf("%s?%s", targetURL, params.Encode())
	fmt.Printf("Calling Share API: %s\n", fullURL)

	req, err := http.NewRequest("GET", fullURL, nil)
	if err != nil { panic(err) }
	req.Header.Set("X-Device-Id", deviceID)
	req.Header.Set("X-Captcha-Token", captchaTokenShare)
	req.Header.Set("Content-Type", "application/json")

	client := http.DefaultClient
	resp, err := client.Do(req)
	if err != nil { panic(err) }
	defer resp.Body.Close()

	body, err := io.ReadAll(resp.Body)
	if err != nil { panic(err) }

	if resp.StatusCode != 200 {
		fmt.Printf("Failed to get share info: %s\n%s\n", resp.Status, string(body))
		return
	}

	var shareResp ShareResponse
	err = json.Unmarshal(body, &shareResp)
	if err != nil { panic(err) }

	fmt.Printf("Share Info Retrieved. Token: %s...\n", shareResp.PassCodeToken[:20])
	if len(shareResp.Files) == 0 {
		fmt.Println("No files found in share root.")
		return
	}
	rootFile := shareResp.Files[0]
	fmt.Printf("Root File: %s (%s) ID: %s\n", rootFile.Name, rootFile.Kind, rootFile.ID)

	if rootFile.Kind == "drive#folder" {
		// 3. List files using /drive/v1/share/detail
		fmt.Println("\n2. Getting Captcha Token for Share Detail...")
		// Use GET:/drive/v1/share/detail ??? Or just try reusing the old one?
		// Usually captcha tokens are one-time or time-bound.
		// Python code calls `captcha_init` for login but doesn't explicitly show it for `get_share_folder`.
		// But `test.py` usually implies authenticated flow.
		// However, for share access without login, we rely on X-Captcha-Token.
		// Let's try to get a NEW captcha token for "GET:/drive/v1/share/detail".

		err := p.AuthCaptchaToken("GET:/drive/v1/share/detail")
		if err != nil {
			fmt.Printf("Error getting captcha token for detail: %v\n", err)
			// Try fallback to "GET:/drive/v1/share" if this fails, or reusing previous?
			// But let's assume specific action string.
		}
		captchaTokenDetail := p.CaptchaToken

		detailURL := "https://api-drive.mypikpak.com/drive/v1/share/detail"
		dParams := url.Values{}
		dParams.Add("share_id", shareID)
		dParams.Add("parent_id", rootFile.ID)
		dParams.Add("pass_code_token", shareResp.PassCodeToken)
		dParams.Add("thumbnail_size", "SIZE_LARGE")
		dParams.Add("limit", "100")
		dParams.Add("order", "6")
		dParams.Add("client_id", clientID)

		fullDetailURL := fmt.Sprintf("%s?%s", detailURL, dParams.Encode())
		fmt.Printf("Calling Share Detail API: %s\n", fullDetailURL)

		dReq, err := http.NewRequest("GET", fullDetailURL, nil)
		if err != nil { panic(err) }
		dReq.Header.Set("X-Device-Id", deviceID)
		dReq.Header.Set("X-Captcha-Token", captchaTokenDetail)
		dReq.Header.Set("Content-Type", "application/json")

		dResp, err := client.Do(dReq)
		if err != nil { panic(err) }
		defer dResp.Body.Close()

		dBody, err := io.ReadAll(dResp.Body)
		if err != nil { panic(err) }

		fmt.Printf("Share Detail Response Status: %s\n", dResp.Status)
		var dObj interface{}
		json.Unmarshal(dBody, &dObj)
		prettyJSON, _ := json.MarshalIndent(dObj, "", "  ")
		fmt.Printf("Share Detail Response Body: %s\n", string(prettyJSON))
	}
}
