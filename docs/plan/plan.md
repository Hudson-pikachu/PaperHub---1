#Lộ trình dựng app

#Giai đoạn 1: 
Mục tiêu có được Prototype giao diện web hiển thị danh sách papers từ cơ sở dữ liệu (chạy local), không cần login. Xây dựng được cấu trúc cơ sở dữ liệu để bỏ vào vài dữ liệu thử nghiệm và hiển thị lên Prototype. Chương trình cũng tự phát hiện được papers trùng để lọc ra khỏi cở sở dữ liệu và đánh dấu đối với các papers gần giống nhau.
+ Chức năng cơ bản sẽ hoàn thành:
    4. Lưu thông tin paper: tiêu đề, abstract, tác giả, ngày công bố, link
    6. Hiển thị danh sách paper mới
    8. Xem chi tiết paper
+ Chức năng nâng cao sẽ hoàn thành:
    2*. Phát hiện paper trùng hoặc gần giống

#Giai đoạn 2: 
Mục tiêu Prototype có thêm chức năng tự động quét dữ liệu từ 1 đến 3 nguồn bài báo khoa học để nạp vào cơ sở dữ liệu, cấu trúc nạp vào được chuẩn hóa theo cấu trúc của cơ sở dữ liệu. Có thêm chức năng login, phân biệt các người dùng khác nhau để bổ sung các chức năng cá nhân hóa trải nghiệm bao gồm cả thông báo cho người dùng khi có paper mới.
+ Chức năng cơ bản sẽ hoàn thành:
    3. Tự động lấy paper mới theo chủ đề
    1. Đăng ký, đăng nhập
    2. Thêm, sửa, xóa chủ đề theo dõi
    9. Lưu paper yêu thích
+ Chức năng nâng cao sẽ hoàn thành:
    3*. Gửi thông báo khi có paper mới
+ Kết quả mong muốn sẽ hoàn thành:
    I. biết nhanh có paper mới nào

#Giai đoạn 3: 
Mục tiêu Prototype có thêm chức năng tóm tắt ý chính của từng papers và lưu tĩnh nội dung tóm tắt vào cơ sở dữ liệu. Khi hiển thị paper lên newsfeed sẽ hiển thị kèm cả tóm tắt. Bổ sung chức năng tìm kiếm paper có thể lọc theo từ khóa, hoặc chủ đề, hoặc từ nội dung tóm tắt.
+ Chức năng cơ bản sẽ hoàn thành:
    5. Tóm tắt ngắn ý chính của paper từ abstract
    7. Tìm kiếm, lọc paper theo từ khóa hoặc chủ đề
+ Kết quả mong muốn sẽ hoàn thành:
    II. đọc nhanh ý chính của paper
    III. tìm được các paper phù hợp với chủ đề mình quan tâm

#Giai đoạn 4: 
Mục tiêu Prototype có thêm chức năng gợi ý các papers liên quan từ nội bộ cơ sở dữ liệu, chấm điểm papers dựa trên số lượt cited (định kỳ phải update lại điểm), thống kê xu hướng chủ đề hot theo tần suất xuất hiện của papers mới.
+ Chức năng nâng cao sẽ hoàn thành:
    1*. Gợi ý paper liên quan
    5*. Chấm điểm paper đáng đọc
    4*. Thống kê xu hướng theo chủ đề
    
#Giai đoạn 5:
Kiểm tra lại tất cả chức năng của Prototype để fix bug và released
    
    