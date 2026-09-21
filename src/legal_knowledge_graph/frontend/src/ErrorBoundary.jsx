import { Component } from 'react'

// Bắt lỗi RENDER bất ngờ (khác với lỗi gọi API, đã bắt riêng trong App.jsx)
// — ví dụ code cố .map() lên field null. Không có lớp này, 1 lỗi render sẽ
// làm React tháo toàn bộ cây và để lại trang trắng.
export default class ErrorBoundary extends Component {
  state = { error: null }

  static getDerivedStateFromError(error) {
    return { error }
  }

  componentDidCatch(error, info) {
    console.error('Lỗi render UI:', error, info)
  }

  render() {
    if (this.state.error) {
      return (
        <div className="error-boundary">
          <p>Có lỗi xảy ra khi hiển thị trang.</p>
          <button onClick={() => this.setState({ error: null })}>Tải lại</button>
        </div>
      )
    }
    return this.props.children
  }
}
