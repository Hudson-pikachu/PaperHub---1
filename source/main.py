from app import create_app

app = create_app()

if __name__ == '__main__':
    # host='0.0.0.0' giúp bạn có thể truy cập từ thiết bị khác trong mạng LAN
    app.run(host='0.0.0.0', port=8080, debug=True)