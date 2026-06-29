# Script Thuyết Trình PaperHub — Đồ Án Nhập Môn Công Nghệ Phần Mềm

> **Tổng thời lượng:** ~4 phút  
> **Tốc độ đọc:** vừa phải, rõ ràng, ngắt nghỉ đúng chỗ  
> **Định dạng:** [MM:SS] Lời thoại *(ghi chú cảnh quay)*

---

## Phần 1: MỤC ĐÍCH & Ý NGHĨA (~35 giây)

---

**[00:00]** Kính chào thầy và các bạn. Nhóm em xin trình bày đồ án môn Nhập môn Công nghệ Phần mềm với đề tài **PaperHub.Site** — Hệ thống theo dõi và tóm tắt bài báo khoa học mới theo chủ đề.  
*(cảnh quay: logo PaperHub fade in + domain paperhub.site, sau đó chuyển sang trang chủ)*

**[00:18]** PaperHub giải quyết vấn đề nan giải của các nhà nghiên cứu và sinh viên: phải tự lục tìm paper mới trên arXiv, Google Scholar mỗi ngày — rất mất thời gian — cộng với rào cản ngôn ngữ khi đa số bài báo viết bằng tiếng Anh. PaperHub tự động tổng hợp paper từ arXiv, tóm tắt ý chính bằng AI, hỗ trợ song ngữ Anh-Việt trên một giao diện web duy nhất. Người dùng chỉ cần chọn chủ đề quan tâm, PaperHub làm phần còn lại.  
*(cảnh quay: người dùng đang scroll trên trang chủ paperhub.site, thấy các paper card với tiêu đề song ngữ)*

---

## Phần 2: CÔNG NGHỆ TRIỂN KHAI (~1 phút 50 giây)

---

**[00:35]** Về kiến trúc công nghệ, chúng em lựa chọn **Python Flask** làm backend framework — nhẹ, linh hoạt và phù hợp với quy mô đồ án. **SQLAlchemy ORM** được dùng để quản lý cơ sở dữ liệu.  
*(cảnh quay: slide show logo Python, Flask, SQLAlchemy — có mũi tên nối thể hiện: Flask nhận request → SQLAlchemy truy vấn Database)*

**[00:55]** Về cơ sở dữ liệu, hệ thống sử dụng **MySQL** trên shared hosting để lưu trữ toàn bộ thông tin người dùng, paper và chủ đề theo dõi.  
*(cảnh quay: slide với logo MySQL, mũi tên "Flask/SQLAlchemy → MySQL Database")*

**[01:15]** Ở tầng AI, chúng em tích hợp **Google Gemini API** với model gemini-2.5-flash-lite. AI đảm nhận hai tác vụ: dịch abstract từ tiếng Anh sang tiếng Việt và tóm tắt ý chính của mỗi paper thành 2-3 câu ngắn gọn.  
*(cảnh quay: slide với logo Google AI Gemini, mũi tên "Abstract EN → Summary VI" và "Summary EN"; chuyển sang web demo — mở một paper bất kỳ thấy phần AI Summary)*

**[01:35]** Nguồn dữ liệu paper được lấy tự động từ **arXiv API** thông qua một **cronjob** — một tác vụ định kỳ chạy trên hosting, cứ mỗi 6 tiếng tự động gọi API, quét các category như Machine Learning, Computer Vision, Natural Language Processing, lưu bài mới vào cơ sở dữ liệu và gọi Gemini để tóm tắt ngay lập tức.  
*(cảnh quay: slide với logo arXiv + cronjob icon đồng hồ, mũi tên "Mỗi 6 tiếng" → Database; chuyển sang web — vào trang admin/dev dashboard, show Fetch History với các dòng "success" và dòng thời gian)*

**[02:00]** Về frontend, chúng em dùng **Tailwind CSS** cho giao diện, **JavaScript thuần** cho các tương tác. Giao diện được thiết kế **responsive** — sử dụng tốt trên cả trình duyệt desktop lẫn mobile. Đặc biệt, toàn bộ hệ thống hỗ trợ **song ngữ Việt-Anh**: người dùng chỉ cần bấm nút toggle là chuyển đổi ngay lập tức.  
*(cảnh quay: mở website trên desktop, thu nhỏ trình duyệt xuống kích thước mobile — UI tự động co giãn; bấm nút chuyển ngôn ngữ từ VI sang EN, thấy nội dung chuyển)*

**[02:20]** Về quy trình triển khai, mã nguồn được quản lý trên **GitHub** ở chế độ private repository. Chúng em thiết lập **webhook** — mỗi khi push code lên GitHub, webhook tự động kích hoạt và deploy phiên bản mới lên hosting. Ứng dụng được host tại domain **paperhub.site** — chúng em đã mua tên miền, thuê shared hosting và cấu hình CI/CD qua webhook.  
*(cảnh quay: slide với logo GitHub + webhook icon, mũi tên "Push code → GitHub → Webhook → paperhub.site")*

---

## Phần 3: CÁC CHỨC NĂNG CHÍNH (~1 phút 35 giây)

---

**[02:40]** Bây giờ chúng em xin trình bày các chức năng chính của hệ thống.

**[02:45]** **Thứ nhất, đăng ký và đăng nhập.** Người dùng có thể tạo tài khoản mới hoặc đăng nhập bằng tài khoản có sẵn, bảo mật qua Flask-Login và session.  
*(cảnh quay: mở modal đăng ký trên web, điền thông tin, đăng ký thành công; sau đó đăng nhập lại)*

**[02:58]** **Thứ hai, quản lý chủ đề theo dõi.** Trong trang cá nhân, người dùng có thể bật hoặc tắt theo dõi các chủ đề như Học máy, Xử lý ngôn ngữ, Thị giác máy tính. Bài viết chưa đọc sẽ hiển thị thông báo trên notification bell.  
*(cảnh quay: vào trang Profile trên web, bấm follow/unfollow một vài chủ đề; quay lại trang chủ thấy notification bell cập nhật số)*

**[03:15]** **Thứ ba, danh sách paper với infinite scroll.** Trang chủ hiển thị 5 bài mới nhất, bấm "Xem thêm bài nghiên cứu" để tải thêm — không cần chuyển trang. Người dùng có thể lọc theo ba tab: bài mới nhất, bài đã lưu, và bài từ chủ đề đang theo dõi.  
*(cảnh quay: scroll trang chủ, bấm "Xem thêm bài nghiên cứu" 2-3 lần; chuyển qua tab "Following" và "Saved")*

**[03:33]** **Thứ tư, tóm tắt AI và song ngữ.** Mỗi paper đều có bản tóm tắt tiếng Việt ngắn gọn do AI tạo, kèm abstract gốc tiếng Anh. Người dùng có thể đọc nhanh ý chính trước khi quyết định có đọc toàn văn hay không.  
*(cảnh quay: bấm vào một paper card trên web, thấy phần AI Summary tiếng Việt, expand abstract gốc; chuyển ngôn ngữ sang EN thấy toàn bộ chuyển thành tiếng Anh)*

**[03:50]** **Thứ năm, tìm kiếm thông minh.** Hệ thống hỗ trợ tìm kiếm paper theo từ khóa, có xếp hạng điểm match — ưu tiên kết quả khớp tiêu đề hơn khớp abstract.  
*(cảnh quay: gõ từ khóa "transformer" vào ô search trên web, xem kết quả trả về có ranking match score)*

**[04:05]** **Thứ sáu, lưu paper yêu thích và đánh giá mức độ đáng đọc.** Người dùng có thể bookmark paper để đọc sau. Hệ thống cũng tự động chấm điểm từng paper dựa trên AI, giúp người dùng biết bài nào đáng đọc nhất.  
*(cảnh quay: bấm icon bookmark trên một paper — nó chuyển sang trạng thái đã lưu; highlight cột score trên mỗi card)*

**[04:20]** Như vậy, PaperHub giúp người dùng: một — biết nhanh có paper mới nào qua notification; hai — đọc nhanh ý chính bằng tiếng Việt qua AI summary; ba — tìm được các paper phù hợp với chủ đề mình quan tâm qua follow và search.  
*(cảnh quay: tổng quan lại trang chủ paperhub.site, chậm dần)*

**[04:35]** Đồ án đã được phát triển theo quy trình có kế hoạch, qua 5 giai đoạn từ dựng prototype, fetch dữ liệu, tích hợp AI, đến scoring và hoàn thiện. Mọi thay đổi đều được quản lý phiên bản qua GitHub private repository và tự động triển khai lên paperhub.site qua webhook. Xin cảm ơn thầy và các bạn đã lắng nghe.  
*(cảnh quay: màn hình tối dần, hiện slide kết thúc với logo PaperHub, domain paperhub.site, các logo công nghệ Flask + MySQL + Gemini + Tailwind)*

---

## TỔNG KẾT THỜI LƯỢNG

| Phần | Nội dung | Timestamp | Thời lượng |
|------|----------|-----------|------------|
| 1 | Mục đích & ý nghĩa | 00:00 – 00:35 | ~35 giây |
| 2 | Công nghệ triển khai | 00:35 – 02:40 | ~2 phút 05 giây |
| 3 | Chức năng chính | 02:40 – 04:35 | ~1 phút 55 giây |
| **Tổng** | | | **~4 phút 35 giây** |

> **Ghi chú:** Các mốc timestamp có thể điều chỉnh linh hoạt theo tốc độ đọc thực tế và thời lượng video cảnh quay. Nếu cần ngắn hơn, có thể lược bớt một số chi tiết ở phần 2.