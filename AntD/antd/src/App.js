import React, { Component } from "react";
import { Layout, Input, Button } from "antd";

// We import our firestore module
import firestore from "./firestore";

import "./App.css";

const { Header, Footer, Content } = Layout;

export default class App extends Component {
  constructor(props) {
    super(props);
    // Set the default state of our application
    this.state = { addingTodo: false, pendingTodo: "" };
    // We want event handlers to share this context
    this.addTodo = this.addTodo.bind(this);
  }
  
  async addTodo(evt) {
    // Set a flag to indicate loading
    this.setState({ addingTodo: true });
    // Add a new todo from the value of the input
    await firestore.collection("todos").add({
      content: this.state.pendingTodo,
      completed: false
    });
    // Remove the loading flag and clear the input
    this.setState({ addingTodo: false, pendingTodo: "" });
  }
  
  render() {
    return (
      <Layout className="App">
        <Header className="App-header">
          <h1>Quick Todo</h1>
        </Header>
        <Content className="App-content">
          <Input
            ref="add-todo-input"
            className="App-add-todo-input"
            size="large"
            placeholder="What needs to be done?"
            disabled={this.state.addingTodo}
            onChange={evt => this.setState({ pendingTodo: evt.target.value })}
            value={this.state.pendingTodo}
            onPressEnter={this.addTodo}
          />
          <Button
            className="App-add-todo-button"
            size="large"
            type="primary"
            onClick={this.addTodo}
            loading={this.state.addingTodo}
          >
            Add Todo
          </Button>
        </Content>
        <Footer className="App-footer">&copy; My Company</Footer>
      </Layout>
    );
  }
}