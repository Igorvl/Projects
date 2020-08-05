import React, { Component } from "react";
import { Layout } from "antd";

import "./App.css";

const { Header, Footer, Content } = Layout;

export default class App extends Component {
  render() {
    return (
      <Layout className="App">
        <Header className="App-header">
          <h1>My Todo</h1>
        </Header>
        <Content className="App-content">Content</Content>
        <Footer className="App-footer">&copy; Copyright</Footer>
      </Layout>
    );
  }
}